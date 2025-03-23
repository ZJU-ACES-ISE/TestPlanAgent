import os
import ast

def create_structure(directory_path):
    """Create the structure of the repository directory by parsing Python files.
    :param directory_path: Path to the repository directory.
    :return: A dictionary representing the structure.
    """
    structure = {}

    for root, _, files in os.walk(directory_path):
        # repo_name = os.path.basename(directory_path)
        relative_root = os.path.relpath(root, directory_path)
        # if relative_root == ".":
        #     relative_root = repo_name
        curr_struct = structure
        for part in relative_root.split(os.sep):
            if relative_root == ".":
                break
            if part not in curr_struct:
                curr_struct[part] = {}
            curr_struct = curr_struct[part]
        for file_name in files:
            if file_name.endswith(".py"):
                file_path = os.path.join(root, file_name)
                class_info, function_names, file_lines = parse_python_file(file_path)
                curr_struct[file_name] = {
                    "classes": class_info,
                    "functions": function_names,
                    "text": file_lines,
                }
            else:
                curr_struct[file_name] = {}

    return structure

def parse_python_file(file_path, file_content=None):
    """Parse a Python file to extract class and function definitions with their line numbers.
    :param file_path: Path to the Python file.
    :return: Class names, function names, and file contents
    """
    if file_content is None:
        try:
            with open(file_path, "r") as file:
                file_content = file.read()
                parsed_data = ast.parse(file_content)
        except Exception as e:  # Catch all types of exceptions
            print(f"Error in file {file_path}: {e}")
            return [], [], ""
    else:
        try:
            parsed_data = ast.parse(file_content)
        except Exception as e:  # Catch all types of exceptions
            print(f"Error in file {file_path}: {e}")
            return [], [], ""

    class_info = []
    function_names = []
    class_methods = set()

    class FunctionCallCollector(ast.NodeVisitor):
        def __init__(self):
            self.function_calls = set()

        def visit_Call(self, node):
            # 处理直接函数调用，如 func()
            if isinstance(node.func, ast.Name):
                self.function_calls.add(node.func.id)
            # 处理属性调用，如 obj.method()
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    self.function_calls.add(f"{node.func.attr}")
            # 继续访问子节点
            self.generic_visit(node)

    for node in ast.walk(parsed_data):
        if isinstance(node, ast.ClassDef):
            methods = []
            for n in node.body:
                if isinstance(n, ast.FunctionDef):
                    collector = FunctionCallCollector()
                    collector.visit(n)
                    
                    methods.append({
                        "name": n.name,
                        "start_line": n.lineno,
                        "end_line": n.end_lineno,
                        "text": file_content.splitlines()[n.lineno - 1 : n.end_lineno],
                        "references": list(collector.function_calls)
                    })
                    class_methods.add(n.name)
            class_info.append(
                {
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "text": file_content.splitlines()[
                        node.lineno - 1 : node.end_lineno
                    ],
                    "methods": methods,
                }
            )
        elif isinstance(node, ast.FunctionDef) and not isinstance(
            node, ast.AsyncFunctionDef
        ):
            if node.name not in class_methods:
                collector = FunctionCallCollector()
                collector.visit(node)
                
                function_names.append(
                    {
                        "name": node.name,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno,
                        "text": file_content.splitlines()[
                            node.lineno - 1 : node.end_lineno
                        ],
                        "references": list(collector.function_calls)
                    }
                )

    return class_info, function_names, file_content.splitlines()