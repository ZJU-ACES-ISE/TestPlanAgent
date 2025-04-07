from tree_sitter_languages import get_parser, get_language
import os
import json
from pathlib import Path

def analyze_code_files(directory):
    # 初始化不同类型文件的解析器
    parsers = {
        'tsx': get_parser('tsx'),
        'ts': get_parser('typescript'),
        'py': get_parser('python'),
        'js': get_parser('javascript')
    }
    
    # 结果将按照文件树结构存储
    results = {}
    
    # 遍历目录中的所有文件
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            ext = file.split('.')[-1]
            
            if ext not in parsers:
                continue
                
            # 获取相对路径用于构建JSON结构
            rel_path = os.path.relpath(file_path, directory)
            
            # 读取文件内容
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                # 解析文件
                parser = parsers[ext]
                tree = parser.parse(content)
                
                # 处理语法树，提取函数和类
                items = extract_definitions(tree.root_node, content, file_path, ext)
                
                if items:
                    # 添加到结果树中
                    add_to_result_tree(results, rel_path, items)
                    
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
    
    return results

def extract_definitions(node, content, file_path, file_type):
    """提取节点中的函数和类定义，包括源代码"""
    items = []
    
    def get_node_text(node):
        """获取节点的源代码文本"""
        return content[node.start_byte:node.end_byte].decode('utf8')
    
    # 根据不同语言处理不同的节点类型
    if file_type in ['tsx', 'ts', 'js']:
        # 提取函数定义
        if node.type == 'function_declaration' or node.type == 'method_definition':
            name = None
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
            
            if name:
                items.append({
                    'type': 'function',
                    'name': name,
                    'code': get_node_text(node),
                    'file': os.path.basename(file_path)
                })
        
        # 提取类定义
        elif node.type == 'class_declaration':
            name = None
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
                    
            if name:
                items.append({
                    'type': 'class',
                    'name': name,
                    'code': get_node_text(node),
                    'file': os.path.basename(file_path)
                })
    
    elif file_type == 'py':
        # 提取Python函数定义
        if node.type == 'function_definition':
            name = None
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
                    
            if name:
                items.append({
                    'type': 'function',
                    'name': name,
                    'code': get_node_text(node),
                    'file': os.path.basename(file_path)
                })
        
        # 提取Python类定义
        elif node.type == 'class_definition':
            name = None
            for child in node.children:
                if child.type == 'identifier':
                    name = child.text.decode('utf8')
                    break
                    
            if name:
                items.append({
                    'type': 'class',
                    'name': name,
                    'code': get_node_text(node),
                    'file': os.path.basename(file_path)
                })
    
    # 递归处理所有子节点，收集结果
    for child in node.children:
        items.extend(extract_definitions(child, content, file_path, file_type))
    
    return items

def add_to_result_tree(results, rel_path, items):
    """将提取的项添加到结果树中"""
    # 按照路径分割文件路径
    path_parts = Path(rel_path).parts
    
    # 沿着路径在结果树中导航
    current = results
    for part in path_parts[:-1]:  # 最后一部分是文件名，单独处理
        if part not in current:
            current[part] = {}
        current = current[part]
    
    # 文件名下存储所有函数和类
    file_name = path_parts[-1]
    if file_name not in current:
        current[file_name] = []
    
    # 添加函数和类
    current[file_name].extend(items)

def save_results_to_json(results, output_file):
    """将结果保存为JSON文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

# 使用示例
if __name__ == "__main__":
    project_dir = "/data/veteran/project/TestPlanAgent/test_project/opentrons"
    output_file = "/data/veteran/project/TestPlanAgent/data_process/project/opentrons_code_structure.json"
    
    results = analyze_code_files(project_dir)
    save_results_to_json(results, output_file)
    
    print(f"代码结构已保存到 {output_file}")