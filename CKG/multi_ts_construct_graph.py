# 扩展的TypeScript解析器 - 修复多进程版本
import json
import pickle
import sys
from pathlib import Path
import multiprocessing
from functools import partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import time
import hashlib
import mmap
import os

import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表
import re
import networkx as nx

from tree_sitter import Language, Parser
from construct_graph import CodeGraph
from copy import deepcopy
# tree_sitter is throwing a FutureWarning
import warnings
warnings.simplefilter("ignore", category=FutureWarning)
from tree_sitter_languages import get_language, get_parser
from collections import Counter, defaultdict, namedtuple
from tqdm import tqdm

Tag = namedtuple("Tag", "rel_fname fname line name kind category info references".split())


def process_typescript_file_worker(file_info):
    """
    独立的worker函数，用于多进程处理单个TypeScript文件
    这个函数必须在模块级别定义，以便pickle序列化
    """
    fname, rel_fname, mentioned_fnames, personalize, structure_data, root_path = file_info
    
    try:
        # 在每个进程中独立创建解析器
        from tree_sitter_languages import get_language, get_parser
        ts_language = get_language("typescript")
        ts_parser = get_parser("typescript")
    except Exception as e:
        return [], {}, f"Error initializing parser: {e}"
    
    personalization = {}
    
    if not Path(fname).is_file():
        return [], personalization, None
        
    if fname in mentioned_fnames:
        personalization[rel_fname] = personalize
    
    # 获取文件结构数据
    ref_fname_lst = rel_fname.split('/')
    s = structure_data
    try:
        for fname_part in ref_fname_lst:
            if fname_part not in s:
                return [], personalization, None
            s = s[fname_part]
        
        if not s or not isinstance(s, dict):
            return [], personalization, None
        
        structure_classes = {item['name']: item for item in s.get('classes', [])}
        structure_functions = {item['name']: item for item in s.get('functions', [])}
        structure_interfaces = {item['name']: item for item in s.get('interfaces', [])}
        structure_class_methods = dict()
        for cls in s.get('classes', []):
            for item in cls.get('methods', []):
                structure_class_methods[item['name']] = item
        structure_all_funcs = {**structure_functions, **structure_class_methods}
    except Exception as e:
        return [], personalization, f"Error processing structure: {e}"

    # 读取文件内容
    try:
        with open(str(fname), "r", encoding='utf-8', errors='replace') as f:
            code = f.read()
    except Exception as e:
        return [], personalization, f"Error reading file: {e}"
    
    # TypeScript查询语句
    query_scm = """
    (class_declaration
      name: (type_identifier) @name.definition.class) @definition.class

    (function_declaration
      name: (identifier) @name.definition.function) @definition.function
    
    (method_definition
      name: (property_identifier) @name.definition.method) @definition.method

    (interface_declaration
      name: (type_identifier) @name.definition.interface) @definition.interface

    (call_expression
      function: (identifier) @name.reference.call) @reference.call

    (call_expression
      function: (member_expression
        property: (property_identifier) @name.reference.call)) @reference.call
    """
    
    try:
        tree = ts_parser.parse(bytes(code, "utf-8"))
    except Exception as e:
        return [], personalization, f"Error parsing file: {e}"
    
    # 获取TypeScript标准库函数
    ts_std_funcs, ts_std_libs = get_typescript_std_funcs(code, fname)
    
    # 执行查询
    try:
        query = ts_language.query(query_scm)
        captures = query.captures(tree.root_node)
    except Exception as e:
        return [], personalization, f"Error executing query: {e}"
    
    tags = []
    for node, tag in captures:
        if tag.startswith("name.definition."):
            kind = "def"
        elif tag.startswith("name.reference."):
            kind = "ref"
        else:
            continue
        
        try:
            tag_name = node.text.decode("utf-8")
        except Exception:
            continue
        
        # 过滤标准库函数
        if tag_name in ts_std_funcs or tag_name in ts_std_libs:
            continue
        
        # 确定类别
        if 'class' in tag:
            category = 'class'
        elif 'interface' in tag:
            category = 'interface'
        else:
            category = 'function'
        
        try:
            if category == 'class':
                if tag_name in structure_classes:
                    class_functions = [item['name'] for item in structure_classes[tag_name]['methods']]
                    if kind == 'def':
                        line_nums = [structure_classes[tag_name]['start_line'], structure_classes[tag_name]['end_line']]
                    else:
                        line_nums = [node.start_point[0], node.end_point[0]]
                    result = Tag(
                        rel_fname=rel_fname,
                        fname=fname,
                        name=tag_name,
                        kind=kind,
                        category=category,
                        info='\n'.join(class_functions),
                        references="",
                        line=line_nums,
                    )
                else:
                    result = Tag(
                        rel_fname=rel_fname,
                        fname=fname,
                        name=tag_name,
                        kind=kind,
                        category=category,
                        info="Class not found in structure",
                        references="",
                        line=[node.start_point[0], node.end_point[0]],
                    )

            elif category == 'function':
                reference = []
                if kind == 'def':
                    if tag_name in structure_all_funcs:
                        cur_cdl = '\n'.join(structure_all_funcs[tag_name]['text'])
                        line_nums = [structure_all_funcs[tag_name]['start_line'], structure_all_funcs[tag_name]['end_line']]
                        reference = structure_all_funcs[tag_name]['references']
                    else:
                        cur_cdl = "Function detail not found in structure"
                        line_nums = [node.start_point[0], node.end_point[0]]
                else:
                    line_nums = [node.start_point[0], node.end_point[0]]
                    cur_cdl = 'function reference'

                result = Tag(
                    rel_fname=rel_fname,
                    fname=fname,
                    name=tag_name,
                    kind=kind,
                    category=category,
                    info=cur_cdl,
                    references='\n'.join(reference),
                    line=line_nums,
                )
                
            elif category == 'interface':
                if tag_name in structure_interfaces:
                    cur_cdl = '\n'.join(structure_interfaces[tag_name]['text'])
                    line_nums = [structure_interfaces[tag_name]['start_line'], structure_interfaces[tag_name]['end_line']]
                else:
                    cur_cdl = "Interface not found in structure"
                    line_nums = [node.start_point[0], node.end_point[0]]
                    
                result = Tag(
                    rel_fname=rel_fname,
                    fname=fname,
                    name=tag_name,
                    kind=kind,
                    category=category,
                    info=cur_cdl,
                    references="",
                    line=line_nums,
                )

            tags.append(result)
            
        except Exception as e:
            continue  # 跳过有问题的标签
    
    return tags, personalization, None


def get_typescript_std_funcs(code, fname):
    """获取TypeScript标准库函数"""
    ts_builtins = [
        'console', 'Array', 'Object', 'String', 'Number', 'Boolean',
        'Date', 'RegExp', 'Error', 'JSON', 'Math', 'Promise',
        'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval'
    ]
    
    std_libs = []
    import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
    imports = re.findall(import_pattern, code)
    
    for imp in imports:
        if not imp.startswith('.'):
            std_libs.append(imp.split('/')[0])
    
    return ts_builtins, std_libs


class TypeScriptCodeGraph(CodeGraph):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化TypeScript解析器
        self.ts_language = get_language("typescript")
        self.ts_parser = get_parser("typescript")
        
        # 多线程缓存
        self._tags_cache = {}
        self._cache_lock = threading.RLock()
        
        self.structure = self.create_typescript_structure(self.root)
    
    def get_code_graph(self, other_files, mentioned_fnames=None):
        if self.max_map_tokens <= 0:
            return
        if not other_files:
            return
        if not mentioned_fnames:
            mentioned_fnames = set()

        max_map_tokens = self.max_map_tokens

        # With no files in the chat, give a bigger view of the entire repo
        MUL = 16
        padding = 4096
        if max_map_tokens and self.max_context_window:
            target = min(max_map_tokens * MUL, self.max_context_window - padding)
        else:
            target = 0

        tags = self.get_tag_files(other_files, mentioned_fnames)
        code_graph = self.tag_to_graph(tags)

        return tags, code_graph
    
    def get_file_content(self, fname):
        """
        高效读取文件内容，大文件使用内存映射
        """
        try:
            file_size = os.path.getsize(fname)
            # 大文件使用内存映射
            if file_size > 1024 * 1024:  # 1MB
                with open(fname, 'r+b') as f:
                    mmapped_file = mmap.mmap(f.fileno(), 0)
                    content = mmapped_file.read().decode('utf-8', errors='replace')
                    mmapped_file.close()
                    return content
            else:
                with open(str(fname), "r", encoding='utf-8', errors='replace') as f:
                    return f.read()
        except Exception as e:
            if hasattr(self, 'io') and self.io:
                self.io.tool_error(f"Error reading file {fname}: {e}")
            else:
                print(f"Error reading file {fname}: {e}")
            return ""

    def get_tags(self, fname, rel_fname):
        """
        带缓存的标签获取方法
        """
        # 检查文件修改时间
        file_mtime = self.get_mtime(fname)
        if file_mtime is None:
            return []
            
        # 创建缓存键
        cache_key = f"{fname}_{file_mtime}"
        md5_key = hashlib.md5(cache_key.encode()).hexdigest()
        
        # 线程安全地检查缓存
        with self._cache_lock:
            if md5_key in self._tags_cache:
                return self._tags_cache[md5_key]
        
        # 缓存未命中，处理文件
        data = list(self.get_typescript_tags_raw(fname, rel_fname))
        
        # 线程安全地更新缓存
        with self._cache_lock:
            self._tags_cache[md5_key] = data
        
        return data

    def get_ranked_tags(self, other_fnames, mentioned_fnames):
        """
        优化的多进程标签获取方法
        """
        tags_of_files = []
        personalization = {}
        
        fnames = sorted(set(other_fnames))
        personalize = 10 / len(fnames) if fnames else 0
        
        # 准备文件信息列表
        file_infos = []
        for fname in fnames:
            if Path(fname).is_file():
                rel_fname = self.get_rel_fname(fname)
                file_infos.append((fname, rel_fname, mentioned_fnames, personalize, self.structure, self.root))
        
        # 根据文件数量决定处理策略
        if len(file_infos) > 1000000:
            # 使用多进程处理
            try:
                print(f"Using multiprocessing for {len(file_infos)} files...")
                
                # 使用ProcessPoolExecutor而不是multiprocessing.Pool
                with ProcessPoolExecutor(max_workers=min(multiprocessing.cpu_count(), len(file_infos))) as executor:
                    # 提交所有任务
                    futures = [executor.submit(process_typescript_file_worker, file_info) for file_info in file_infos]
                    
                    # 收集结果
                    for future in tqdm(futures, desc="Processing files with multiprocessing"):
                        try:
                            tags, p_dict, error = future.result(timeout=60)
                            if error:
                                print(f"Warning: {error}")
                                continue
                            if tags:
                                tags_of_files.extend(tags)
                            personalization.update(p_dict)
                        except Exception as e:
                            print(f"Error processing file: {e}")
                            continue
                
                return tags_of_files
                
            except Exception as e:
                print(f"Multiprocessing failed, falling back to multithreading: {e}")
                # 回退到多线程处理
                return self._get_tags_with_threading(file_infos)
        else:
            # 文件数量少，使用多线程处理
            return self._get_tags_sequential(file_infos)

    def _get_tags_with_threading(self, file_infos):
        """
        使用多线程处理文件标签获取
        """
        tags_of_files = []
        personalization = {}
        
        print(f"Using multithreading for {len(file_infos)} files...")
        
        def process_file_thread(file_info):
            fname, rel_fname, mentioned_fnames, personalize, structure_data, root_path = file_info
            
            if fname in mentioned_fnames:
                return self.get_tags(fname, rel_fname), {rel_fname: personalize}
            else:
                return self.get_tags(fname, rel_fname), {}
        
        # 使用ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(32, len(file_infos))) as executor:
            futures = [executor.submit(process_file_thread, file_info) for file_info in file_infos]
            
            for future in tqdm(futures, desc="Processing files with multithreading"):
                try:
                    tags, p_dict = future.result()
                    if tags:
                        tags_of_files.extend(tags)
                    personalization.update(p_dict)
                except Exception as e:
                    print(f"Error in thread processing: {e}")
                    continue
        
        return tags_of_files

    def _get_tags_sequential(self, fnames, mentioned_fnames):
        """
        顺序处理文件标签获取（作为最后的回退方案）
        """
        tags_of_files = []
        personalize = 10 / len(fnames) if fnames else 0
        
        print("Using sequential processing...")
        for fname in tqdm(fnames, desc="Processing files sequentially"):
            if not Path(fname).is_file():
                if fname not in self.warned_files:
                    if Path(fname).exists():
                        print(f"Code graph can't include {fname}, it is not a normal file")
                    else:
                        print(f"Code graph can't include {fname}, it no longer exists")
                    self.warned_files.add(fname)
                continue

            rel_fname = self.get_rel_fname(fname)
            tags = self.get_tags(fname, rel_fname)

            if tags:
                tags_of_files.extend(tags)

        return tags_of_files
    
    def get_tag_files(self, other_files, mentioned_fnames=None):
        try:
            start_time = time.time()
            tags = self.get_ranked_tags(other_files, mentioned_fnames)
            end_time = time.time()
            print(f"Tag extraction completed in {end_time - start_time:.2f} seconds")
            return tags
        except RecursionError:
            if hasattr(self, 'io') and self.io:
                self.io.tool_error("Disabling code graph, git repo too large?")
            else:
                print("Disabling code graph, git repo too large?")
            self.max_map_tokens = 0
            return []
        except Exception as e:
            if hasattr(self, 'io') and self.io:
                self.io.tool_error(f"Error in tag extraction: {str(e)}")
            else:
                print(f"Error in tag extraction: {str(e)}")
            return []

    def tag_to_graph(self, tags):
        """
        批量构建图以提高性能
        """
        if not tags:
            return nx.MultiDiGraph()
            
        # 收集所有节点和边
        nodes = []
        edges = []
        node_names = set()
        
        # 第一遍收集定义节点
        for tag in tags:
            if tag.kind == 'def':
                nodes.append((tag.name, {
                    'category': tag.category, 
                    'info': tag.info, 
                    'fname': tag.fname, 
                    'line': tag.line, 
                    'kind': tag.kind, 
                    'references': tag.references
                }))
                node_names.add(tag.name)
        
        # 第二遍收集引用节点（如果还没有添加的话）
        for tag in tags:
            if tag.kind != 'def' and tag.name not in node_names:
                nodes.append((tag.name, {
                    'category': tag.category, 
                    'info': tag.info, 
                    'fname': tag.fname, 
                    'line': tag.line, 
                    'kind': tag.kind, 
                    'references': tag.references
                }))
                node_names.add(tag.name)
        
        # 收集边
        for tag in tags:
            if tag.category == 'class' and tag.info:
                class_funcs = tag.info.split('\n')
                for f in class_funcs:
                    f = f.strip()
                    if f:
                        edges.append((tag.name, f))
            if tag.category == 'function' and tag.kind == 'def' and tag.references:
                func_refs = tag.references.split('\n')
                for f in func_refs:
                    f = f.strip()
                    if f:
                        edges.append((tag.name, f))
        
        # 一次性创建图
        G = nx.MultiDiGraph()
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        
        return G
    
    def create_typescript_structure(self, directory_path):
        """
        使用多线程创建TypeScript结构
        """
        structure = {}
        
        # 收集所有TypeScript文件
        ts_files = []
        for root, _, files in os.walk(directory_path):
            for file_name in files:
                if file_name.endswith((".ts", ".tsx")):
                    file_path = os.path.join(root, file_name)
                    relative_root = os.path.relpath(root, directory_path)
                    ts_files.append((file_path, relative_root, file_name))
        
        print(f"Found {len(ts_files)} TypeScript files, parsing structure...")
        
        # 使用多线程解析文件结构（I/O密集型任务）
        if len(ts_files) > 10:
            with ThreadPoolExecutor(max_workers=min(32, len(ts_files))) as executor:
                # 提交解析任务
                future_to_file = {
                    executor.submit(self._parse_file_structure, file_path): 
                    (file_path, relative_root, file_name)
                    for file_path, relative_root, file_name in ts_files
                }
                
                # 收集结果
                with tqdm(total=len(ts_files), desc="Parsing structure with threading") as pbar:
                    for future in future_to_file:
                        file_path, relative_root, file_name = future_to_file[future]
                        try:
                            file_structure = future.result()
                            if file_structure:
                                self._add_to_structure(structure, relative_root, file_name, file_structure)
                        except Exception as e:
                            print(f"Error parsing {file_path}: {e}")
                        finally:
                            pbar.update(1)
        else:
            # 文件数量少时使用单线程
            for file_path, relative_root, file_name in tqdm(ts_files, desc="Parsing structure sequentially"):
                try:
                    file_structure = self._parse_file_structure(file_path)
                    if file_structure:
                        self._add_to_structure(structure, relative_root, file_name, file_structure)
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
                    
        return structure
    
    def _parse_file_structure(self, file_path):
        """
        解析单个文件的结构
        """
        try:
            class_info, function_names, interface_names, file_lines = self.parse_typescript_file(file_path)
            return {
                "classes": class_info,
                "functions": function_names,
                "interfaces": interface_names,
                "text": file_lines,
            }
        except Exception as e:
            print(f"Error parsing file structure {file_path}: {e}")
            return None
    
    def _add_to_structure(self, structure, relative_root, file_name, file_structure):
        """
        线程安全地将文件结构添加到总结构中
        """
        curr_struct = structure
        
        for part in relative_root.split(os.sep):
            if relative_root == ".":
                break
            if part not in curr_struct:
                curr_struct[part] = {}
            curr_struct = curr_struct[part]
        
        curr_struct[file_name] = file_structure
    
    def parse_typescript_file(self, file_path, file_content=None):
        """
        解析TypeScript文件
        """
        if file_content is None:
            try:
                with open(file_path, "r", encoding='utf-8') as file:
                    file_content = file.read()
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
                return [], [], [], []
        
        try:
            tree = self.ts_parser.parse(bytes(file_content, "utf-8"))
        except Exception as e:
            print(f"Error parsing TypeScript file {file_path}: {e}")
            return [], [], [], []
        
        class_info = []
        function_names = []
        interface_names = []

        # TypeScript特有的AST节点处理
        for node in self._traverse_typescript_nodes(tree.root_node, file_content):
            if node['type'] == 'class':
                class_info.append(node)
            elif node['type'] == 'function':
                function_names.append(node)
            elif node['type'] == 'interface':
                interface_names.append(node)
                
        return class_info, function_names, interface_names, file_content.splitlines()
    
    def get_typescript_tags_raw(self, fname, rel_fname):
        """
        单线程版本的TypeScript标签获取方法
        """
        # 调用模块级别的worker函数
        mentioned_fnames = set()  # 单线程版本不需要这个
        personalize = 0
        file_info = (fname, rel_fname, mentioned_fnames, personalize, self.structure, self.root)
        
        tags, _, error = process_typescript_file_worker(file_info)
        if error:
            print(f"Error processing {fname}: {error}")
            return []
        return tags
    
    # 保持其他辅助方法不变
    def _extract_interface_info(self, node, source_code):
        """提取接口信息"""
        interface_name = None
        
        for child in node.children:
            if child.type == 'type_identifier':
                interface_name = source_code[child.start_byte:child.end_byte]
                break
        
        if not interface_name:
            return None
        
        return {
            'type': 'interface',
            'name': interface_name,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'text': source_code.splitlines()[node.start_point[0]:node.end_point[0] + 1],
            'methods': []
        }

    def _traverse_typescript_nodes(self, node, source_code):
        """遍历TypeScript AST节点"""
        results = []
        
        def traverse(node, source_code):
            if node.type == 'class_declaration':
                class_data = self._extract_class_info(node, source_code)
                if class_data:
                    results.append(class_data)
            elif node.type in ['function_declaration', 'method_definition', 'arrow_function']:
                func_data = self._extract_function_info(node, source_code)
                if func_data:
                    results.append(func_data)
            elif node.type == 'interface_declaration':
                interface_data = self._extract_interface_info(node, source_code)
                if interface_data:
                    results.append(interface_data)
            
            for child in node.children:
                traverse(child, source_code)
        
        traverse(node, source_code)
        return results
    
    def _get_function_name(self, node, source_code):
        """获取函数名"""
        if node.type == 'function_declaration':
            for child in node.children:
                if child.type == 'identifier':
                    return source_code[child.start_byte:child.end_byte]
        elif node.type == 'method_definition':
            for child in node.children:
                if child.type == 'property_identifier':
                    return source_code[child.start_byte:child.end_byte]
        elif node.type == 'arrow_function':
            return "anonymous_arrow_function"
        return None
    
    def _extract_class_methods(self, class_body_node, source_code):
        """提取类方法"""
        methods = []
        for child in class_body_node.children:
            if child.type == 'method_definition':
                method_name = None
                for grandchild in child.children:
                    if grandchild.type == 'property_identifier':
                        method_name = source_code[grandchild.start_byte:grandchild.end_byte]
                        break
                if method_name:
                    methods.append({
                        'name': method_name,
                        'start_line': child.start_point[0] + 1,
                        'end_line': child.end_point[0] + 1,
                        'text': source_code.splitlines()[child.start_point[0]:child.end_point[0] + 1],
                        'references': []
                    })
        return methods

    def _extract_class_info(self, node, source_code):
        """提取类信息"""
        class_name = None
        methods = []
        
        for child in node.children:
            if child.type == 'identifier':
                class_name = source_code[child.start_byte:child.end_byte]
                break
        
        if not class_name:
            return None
        
        for child in node.children:
            if child.type == 'class_body':
                methods = self._extract_class_methods(child, source_code)
                break
        
        return {
            'type': 'class',
            'name': class_name,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'text': source_code.splitlines()[node.start_point[0]:node.end_point[0] + 1],
            'methods': methods
        }
    
    def _extract_function_calls(self, node, source_code):
        """提取函数调用"""
        calls = []
        
        def find_calls(node):
            if node.type == 'call_expression':
                func_node = node.children[0] if node.children else None
                if func_node:
                    if func_node.type == 'identifier':
                        call_name = source_code[func_node.start_byte:func_node.end_byte]
                        calls.append(call_name)
                    elif func_node.type == 'member_expression':
                        for child in func_node.children:
                            if child.type == 'property_identifier':
                                call_name = source_code[child.start_byte:child.end_byte]
                                calls.append(call_name)
                                break
            
            for child in node.children:
                find_calls(child)
        
        find_calls(node)
        return calls

    def _extract_function_info(self, node, source_code):
        """提取函数信息"""
        func_name = self._get_function_name(node, source_code)
        if not func_name:
            return None
        
        references = self._extract_function_calls(node, source_code)
        
        return {
            'type': 'function',
            'name': func_name,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'text': source_code.splitlines()[node.start_point[0]:node.end_point[0] + 1],
            'references': references
        }
    
    def find_typescript_files(self, directories):
        """查找TypeScript文件"""
        ts_files = []
        for directory in directories:
            if Path(directory).is_dir():
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if file.endswith(('.ts', '.tsx')):
                            ts_files.append(os.path.join(root, file))
            else:
                if directory.endswith(('.ts', '.tsx')):
                    ts_files.append(directory)
        return ts_files

    def find_files(self, dir_list):
        """
        使用多线程查找TypeScript文件
        """
        all_files = []
        
        with ThreadPoolExecutor(max_workers=min(32, len(dir_list) * 2)) as executor:
            # 为每个目录提交任务
            future_to_dir = {
                executor.submit(self.find_typescript_files, [d]): d 
                for d in dir_list if isinstance(d, (str, Path))
            }
            
            # 处理结果
            for future in future_to_dir:
                try:
                    files = future.result()
                    all_files.extend(files)
                except Exception as exc:
                    print(f'Error finding files: {exc}')
        
        # 过滤保留TypeScript文件
        return [item for item in all_files if item.endswith(('.ts', '.tsx'))]


# 使用TypeScript代码图
if __name__ == "__main__":
    try:
        # TypeScript项目路径
        if len(sys.argv) > 1:
            dir_name = sys.argv[1]
        else:
            dir_name = "/data/veteran/project/TestPlanAgent/test_project/App"
        
        repo_name = dir_name.split(os.path.sep)[-1]
        
        # 创建TypeScript代码图 - 使用修复的多进程版本
        print("Initializing TypeScript Code Graph with fixed multiprocessing support...")
        ts_code_graph = TypeScriptCodeGraph(root=dir_name, verbose=True)
        
        # 查找TypeScript文件
        print("Finding TypeScript files...")
        ts_files = ts_code_graph.find_files([dir_name])
        print(f"Found {len(ts_files)} TypeScript files")
        
        if not ts_files:
            print("No TypeScript files found!")
            sys.exit(1)
        
        # 构建代码图 - 修复的多进程版本
        print("Building code graph (this may take some time for large repositories)...")
        start_time = time.time()
        
        # 处理所有文件
        tags, G = ts_code_graph.get_code_graph(ts_files)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 打印统计信息
        print("-" * 50)
        print(f"🏅 Successfully constructed the TypeScript code graph for repo: {dir_name}")
        print(f"   Processing time: {processing_time:.2f} seconds")
        print(f"   Files processed: {len(ts_files)}")
        print(f"   Average time per file: {processing_time/len(ts_files):.3f} seconds")
        if tags:
            print(f"   Tags collected: {len(tags)}")
        if G:
            print(f"   Graph nodes: {len(G.nodes)}")
            print(f"   Graph edges: {len(G.edges)}")
        print("-" * 50)

        # 保存结果
        if G and tags:
            # 确保输出目录存在
            output_dir = f'{os.getcwd()}/CKG'
            os.makedirs(output_dir, exist_ok=True)
            
            # 保存图结构
            with open(f'{output_dir}/{repo_name}_graph.pkl', 'wb') as f:
                pickle.dump(G, f)
            
            # 保存标签信息
            with open(f'{output_dir}/{repo_name}_tags.json', 'w') as f:
                for tag in tags:
                    line = json.dumps({
                        "fname": tag.fname,
                        'rel_fname': tag.rel_fname,
                        'line': tag.line,
                        'name': tag.name,
                        'kind': tag.kind,
                        'category': tag.category,
                        'info': tag.info,
                        'references': tag.references,
                    }, ensure_ascii=False)
                    f.write(line + '\n')
            
            print(f"🏅 Successfully cached code graph and node tags in directory '{output_dir}'")
            
            # 输出统计信息
            if tags:
                tag_stats = Counter(tag.category for tag in tags)
                print(f"Tag category statistics: {dict(tag_stats)}")
                
                def_stats = Counter(tag.kind for tag in tags)
                print(f"Definition/Reference statistics: {dict(def_stats)}")
                
                # 输出文件分布统计
                file_stats = Counter(tag.rel_fname for tag in tags)
                print(f"Top 10 files by tag count:")
                for fname, count in file_stats.most_common(10):
                    print(f"  {fname}: {count} tags")
        else:
            print("⚠️ Code graph construction failed or no valid tags found")
            
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)