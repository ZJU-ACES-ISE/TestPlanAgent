# 扩展的TypeScript解析器
import json
import pickle
import sys
from pathlib import Path

import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表
import re
import os
# import tree_sitter_typescript as ts_typescript
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


class TypeScriptCodeGraph(CodeGraph):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化TypeScript解析器
        self.ts_language = get_language("typescript")
        self.ts_parser = get_parser("typescript")
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
    
    def get_tags(self, fname, rel_fname):
        # Check if the file is in the cache and if the modification time has not changed
        file_mtime = self.get_mtime(fname)
        if file_mtime is None:
            return []
        # miss!
        data = list(self.get_typescript_tags_raw(fname, rel_fname))
        return data

    def get_ranked_tags(self, other_fnames, mentioned_fnames):
        # defines = defaultdict(set)
        # references = defaultdict(list)
        # definitions = defaultdict(set)
        
        tags_of_files = list()

        personalization = dict()

        fnames = set(other_fnames)
        # chat_rel_fnames = set()

        fnames = sorted(fnames)

        # Default personalization for unspecified files is 1/num_nodes
        # https://networkx.org/documentation/stable/_modules/networkx/algorithms/link_analysis/pagerank_alg.html#pagerank
        personalize = 10 / len(fnames)

        for fname in tqdm(fnames):
            if not Path(fname).is_file():
                if fname not in self.warned_files:
                    if Path(fname).exists():
                        self.io.tool_error(
                            f"Code graph can't include {fname}, it is not a normal file"
                        )
                    else:
                        self.io.tool_error(f"Code graph can't include {fname}, it no longer exists")

                self.warned_files.add(fname)
                continue

            # dump(fname)
            rel_fname = self.get_rel_fname(fname)

            # if fname in chat_fnames:
            #     personalization[rel_fname] = personalize
            #     chat_rel_fnames.add(rel_fname)

            if fname in mentioned_fnames:
                personalization[rel_fname] = personalize
            
            tags = list(self.get_tags(fname, rel_fname))

            if tags is None:
                continue

            tags_of_files.extend(tags)

        return tags_of_files
    
    def get_tag_files(self, other_files, mentioned_fnames=None):
        try:
            tags = self.get_ranked_tags(other_files, mentioned_fnames)
            return tags
        except RecursionError:
            self.io.tool_error("Disabling code graph, git repo too large?")
            self.max_map_tokens = 0
            return

    def tag_to_graph(self, tags):
        
        G = nx.MultiDiGraph()
        for tag in tags:
            if tag.kind == 'def':
                G.add_node(tag.name, category=tag.category, info=tag.info, fname=tag.fname, line=tag.line, kind=tag.kind, references=tag.references)
        for tag in tags:
            if tag.kind != 'def' and tag.name not in G.nodes():
                G.add_node(tag.name, category=tag.category, info=tag.info, fname=tag.fname, line=tag.line, kind=tag.kind, references=tag.references)

        for tag in tags:
            if tag.category == 'class':
                class_funcs = tag.info.split('\n')
                for f in class_funcs:
                    G.add_edge(tag.name, f.strip())
            if tag.category == 'function' and tag.kind == 'def':
                func_func = tag.references.split('\n')
                for f in func_func:
                    G.add_edge(tag.name, f.strip())
        # tags_ref = [tag for tag in tags if tag.kind == 'ref']
        # tags_def = [tag for tag in tags if tag.kind == 'def']
        # # 函数info存放调用过的函数
        # for tag in tags_ref:
        #     for tag_def in tags_def:
        #         if tag.name == tag_def.name:
        #             G.add_edge(tag.name, tag_def.name)
        return G
    
    def create_typescript_structure(self, directory_path):
        """扩展create_structure函数支持TypeScript"""
        structure = {}
        
        for root, _, files in os.walk(directory_path):
            relative_root = os.path.relpath(root, directory_path)
            curr_struct = structure
            
            for part in relative_root.split(os.sep):
                if relative_root == ".":
                    break
                if part not in curr_struct:
                    curr_struct[part] = {}
                curr_struct = curr_struct[part]
                
            for file_name in files:
                if file_name.endswith((".ts", ".tsx")):
                    file_path = os.path.join(root, file_name)
                    class_info, function_names, interface_names, file_lines = self.parse_typescript_file(file_path)
                    curr_struct[file_name] = {
                        "classes": class_info,
                        "functions": function_names,
                        "interfaces": interface_names,
                        "text": file_lines,
                    }
                else:
                    curr_struct[file_name] = {}
                    
        return structure
    
    def parse_typescript_file(self, file_path, file_content=None):
        """解析TypeScript文件"""
        if file_content is None:
            try:
                with open(file_path, "r", encoding='utf-8') as file:
                    file_content = file.read()
            except Exception as e:
                print(f"Error in file {file_path}: {e}")
                return [], [], ""
        
        try:
            tree = self.ts_parser.parse(bytes(file_content, "utf-8"))
        except Exception as e:
            print(f"Error parsing TypeScript file {file_path}: {e}")
            return [], [], ""
        
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
    
    def _extract_interface_info(self, node, source_code):
        """提取接口信息"""
        interface_name = None
        
        # 查找接口名
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
            'methods': []  # 接口的方法签名
        }

    def _traverse_typescript_nodes(self, node, source_code):
        """遍历TypeScript AST节点"""
        results = []
        
        def traverse(node, source_code):
            # 处理类定义
            if node.type == 'class_declaration':
                class_data = self._extract_class_info(node, source_code)
                if class_data:
                    results.append(class_data)
            
            # 处理函数定义
            elif node.type in ['function_declaration', 'method_definition', 'arrow_function']:
                func_data = self._extract_function_info(node, source_code)
                if func_data:
                    results.append(func_data)
            
            # 处理接口定义 (TypeScript特有)
            elif node.type == 'interface_declaration':
                interface_data = self._extract_interface_info(node, source_code)
                if interface_data:
                    results.append(interface_data)
            
            # 递归处理子节点
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
            # 箭头函数可能需要特殊处理
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
                        'references': []  # 可以进一步提取方法内的函数调用
                    })
        return methods

    def _extract_class_info(self, node, source_code):
        """提取类信息"""
        class_name = None
        methods = []
        
        # 查找类名
        for child in node.children:
            if child.type == 'identifier':
                class_name = source_code[child.start_byte:child.end_byte]
                break
        
        if not class_name:
            return None
        
        # 查找方法
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
                        # 处理 obj.method() 形式的调用
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
        
        # 提取函数调用
        references = self._extract_function_calls(node, source_code)
        
        return {
            'type': 'function',
            'name': func_name,
            'start_line': node.start_point[0] + 1,
            'end_line': node.end_point[0] + 1,
            'text': source_code.splitlines()[node.start_point[0]:node.end_point[0] + 1],
            'references': references
        }
    
    def get_typescript_tags_raw(self, fname, rel_fname):
        """TypeScript版本的get_tags_raw"""
        # 使用TypeScript结构数据
        ref_fname_lst = rel_fname.split('/')
        s = deepcopy(self.structure)
        for fname_part in ref_fname_lst:
            if fname_part not in s:
                return
            s = s[fname_part]
        
        structure_classes = {item['name']: item for item in s['classes']}
        structure_functions = {item['name']: item for item in s['functions']}
        structure_interfaces = {item['name']: item for item in s['interfaces']}
        structure_class_methods = dict()
        for cls in s['classes']:
            for item in cls['methods']:
                structure_class_methods[item['name']] = item
        structure_all_funcs = {**structure_functions, **structure_class_methods}

        with open(str(fname), "r", encoding='utf-8') as f:
            code = f.read()
        
        # TypeScript特有的查询语句
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
        
        tree = self.ts_parser.parse(bytes(code, "utf-8"))
        
        # 获取TypeScript标准库函数
        ts_std_funcs, ts_std_libs = self.get_typescript_std_funcs(code, fname)
        
        # 执行查询
        query = self.ts_language.query(query_scm)
        captures = query.captures(tree.root_node)
        
        for node, tag in captures:
            if tag.startswith("name.definition."):
                kind = "def"
            elif tag.startswith("name.reference."):
                kind = "ref"
            else:
                continue
            
            tag_name = node.text.decode("utf-8")
            
            # 过滤标准库函数
            if tag_name in ts_std_funcs or tag_name in ts_std_libs:
                continue
            
            # 确定类别
            if 'class' in tag:
                category = 'class'
            elif 'interface' in tag:
                category = 'interface'  # TypeScript特有
            else:
                category = 'function'
            
            if category == 'class':
                # try:
                #     class_functions = self.get_class_functions(tree_ast, tag_name)
                # except:
                #     class_functions = "None"
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
                        info='\n'.join(class_functions), # list unhashable, use string instead
                        references="",
                        line=line_nums,
                    )
                else:
                    # If the class is not in structure_classes, we'll create a basic Tag
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
                    # func_block = self.get_func_block(cur_cdl, code)
                    # cur_cdl =func_block
                    
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
                cur_cdl = '\n'.join(structure_interfaces[tag_name]['text'])
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

            yield result
    
    def get_typescript_std_funcs(self, code, fname):
        """获取TypeScript标准库函数"""
        # TypeScript内置对象和函数
        ts_builtins = [
            'console', 'Array', 'Object', 'String', 'Number', 'Boolean',
            'Date', 'RegExp', 'Error', 'JSON', 'Math', 'Promise',
            'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval'
        ]
        
        # 分析import语句
        std_libs = []
        import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
        imports = re.findall(import_pattern, code)
        
        for imp in imports:
            if not imp.startswith('.'):  # 非相对路径导入
                std_libs.append(imp.split('/')[0])
        
        return ts_builtins, std_libs
    
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
    
# 使用TypeScript代码图
if __name__ == "__main__":
    # TypeScript项目
    dir_name = "/data/veteran/project/TestPlanAgent/test_project/App"
    repo_name = dir_name.split(os.path.sep)[-1]
    
    # 创建TypeScript代码图
    ts_code_graph = TypeScriptCodeGraph(root=dir_name)
    
    # 查找TypeScript文件
    ts_files = ts_code_graph.find_typescript_files([dir_name])
    
    # 构建代码图
    tags, G = ts_code_graph.get_code_graph(ts_files[40:100])
    
    print(f"TypeScript项目代码图构建完成:")
    print(f"节点数: {len(G.nodes)}")
    print(f"边数: {len(G.edges)}")

    with open(f'{os.getcwd()}/CKG/{repo_name}_graph.pkl', 'wb') as f:
        pickle.dump(G, f)
    
    for tag in tags:
        with open(f'{os.getcwd()}/CKG/{repo_name}_tags.json', 'a+') as f:
            line = json.dumps({
                "fname": tag.fname,
                'rel_fname': tag.rel_fname,
                'line': tag.line,
                'name': tag.name,
                'kind': tag.kind,
                'category': tag.category,
                'info': tag.info,
                'references': tag.references,
            })
            f.write(line+'\n')
    print(f"🏅 Successfully cached code graph and node tags in directory ''{os.getcwd()} + /CKG''")