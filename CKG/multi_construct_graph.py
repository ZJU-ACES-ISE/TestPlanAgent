# This file is adapted from the following sources:
# RepoMap: https://github.com/paul-gauthier/aider/blob/main/aider/repomap.py
# Agentless: https://github.com/OpenAutoCoder/Agentless/blob/main/get_repo_structure/get_repo_structure.py
# grep-ast: https://github.com/paul-gauthier/grep-ast

import sys
from pathlib import Path
import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

import colorsys
import os
import random
import re
import warnings
import hashlib
import mmap
import multiprocessing
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict, namedtuple
from pathlib import Path
import builtins
import inspect
import networkx as nx
from grep_ast import TreeContext, filename_to_lang
from pygments.lexers import guess_lexer_for_filename
from pygments.token import Token
from pygments.util import ClassNotFound
from tqdm import tqdm
import ast
import pickle
import json
from copy import deepcopy
from CKG.utils import create_structure

# tree_sitter is throwing a FutureWarning
warnings.simplefilter("ignore", category=FutureWarning)
from tree_sitter_languages import get_language, get_parser

Tag = namedtuple("Tag", "rel_fname fname line name kind category info references".split())


class CodeGraph:

    warned_files = set()

    def __init__(
        self,
        map_tokens=1024,
        root=None,
        main_model=None,
        io=None,
        repo_content_prefix=None,
        verbose=False,
        max_context_window=None,
    ):
        self.io = io
        self.verbose = verbose

        if not root:
            root = os.getcwd()
        self.root = root

        self.max_map_tokens = map_tokens
        self.max_context_window = max_context_window

        # self.token_count = main_model.token_count
        self.repo_content_prefix = repo_content_prefix
        self.structure = create_structure(self.root)
        
        # Initialize caches
        self._tags_cache = {}
        self.tree_cache = {}
        
        # Set the multiprocessing method to spawn for better compatibility
        multiprocessing.set_start_method('spawn', force=True)

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

    def get_tag_files(self, other_files, mentioned_fnames=None):
        try:
            tags = self.get_ranked_tags(other_files, mentioned_fnames)
            return tags
        except RecursionError:
            if self.io:
                self.io.tool_error("Disabling code graph, git repo too large?")
            else:
                print("Disabling code graph, git repo too large?")
            self.max_map_tokens = 0
            return []

    def tag_to_graph(self, tags):
        """
        Build a graph from the tags with batch processing for better performance.
        """
        # Collect all nodes and edges first
        nodes = []
        edges = []
        node_names = set()
        
        # First pass to collect def nodes
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
        
        # Second pass for ref nodes not already added
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
        
        # Collect edges
        for tag in tags:
            if tag.category == 'class':
                class_funcs = tag.info.split('\n')
                for f in class_funcs:
                    if f.strip():
                        edges.append((tag.name, f.strip()))
            if tag.category == 'function' and tag.kind == 'def':
                func_func = tag.references.split('\n')
                for f in func_func:
                    if f.strip():
                        edges.append((tag.name, f.strip()))
        
        # Create graph in one operation
        G = nx.MultiDiGraph()
        G.add_nodes_from(nodes)
        G.add_edges_from(edges)
        
        return G

    def get_rel_fname(self, fname):
        return os.path.relpath(fname, self.root)

    def split_path(self, path):
        path = os.path.relpath(path, self.root)
        return [path + ":"]

    def get_mtime(self, fname):
        try:
            return os.path.getmtime(fname)
        except FileNotFoundError:
            if self.io:
                self.io.tool_error(f"File not found error: {fname}")
            else:
                print(f"File not found error: {fname}")
            return None

    def get_class_functions(self, tree, class_name):
        class_functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        class_functions.append(item.name)

        return class_functions

    def get_func_block(self, first_line, code_block):
        first_line_escaped = re.escape(first_line)
        pattern = re.compile(rf'({first_line_escaped}.*?)(?=(^\S|\Z))', re.DOTALL | re.MULTILINE)
        match = pattern.search(code_block)

        return match.group(0) if match else None

    def std_proj_funcs(self, code, fname):
        """
        Analyze the *import* part of a py file.
        Input: code for fname
        output: [standard functions]
        Note that the project_dependent libraries should have specific project names.
        """
        std_libs = []
        std_funcs = []
        
        try:
            tree = ast.parse(code)
            codelines = code.split('\n')

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    # identify the import statement
                    import_statement = codelines[node.lineno-1]
                    for alias in node.names:
                        import_name = alias.name.split('.')[0]
                        if import_name in fname:
                            continue
                        else:
                            # execute the import statement to find callable functions
                            import_statement = import_statement.strip()
                            try:
                                exec(import_statement)
                            except:
                                continue
                            std_libs.append(alias.name)
                            eval_name = alias.name if alias.asname is None else alias.asname
                            std_funcs.extend([name for name, member in inspect.getmembers(eval(eval_name)) if callable(member)])

                if isinstance(node, ast.ImportFrom):
                    # execute the import statement
                    import_statement = codelines[node.lineno-1]
                    if node.module is None:
                        continue
                    module_name = node.module.split('.')[0]
                    if module_name in fname:
                        continue
                    else:
                        # handle imports with parentheses
                        if "(" in import_statement:
                            for ln in range(node.lineno-1, len(codelines)):
                                if ")" in codelines[ln]:
                                    code_num = ln
                                    break
                            import_statement = '\n'.join(codelines[node.lineno-1:code_num+1])
                        import_statement = import_statement.strip()
                        try:
                            exec(import_statement)
                        except:
                            continue
                        for alias in node.names:
                            std_libs.append(alias.name)
                            eval_name = alias.name if alias.asname is None else alias.asname
                            if eval_name == "*":
                                continue
                            std_funcs.extend([name for name, member in inspect.getmembers(eval(eval_name)) if callable(member)])
        except Exception as e:
            if self.verbose:
                print(f"Error in std_proj_funcs: {e}")
            return [], []
            
        return std_funcs, std_libs

    def get_file_content(self, fname):
        """
        Efficiently read file content using memory mapping for large files.
        """
        try:
            file_size = os.path.getsize(fname)
            # Use mmap for larger files (>1MB)
            if file_size > 1024 * 1024:
                with open(fname, 'r+b') as f:
                    mmapped_file = mmap.mmap(f.fileno(), 0)
                    content = mmapped_file.read().decode('utf-8', errors='replace')
                    mmapped_file.close()
                    return content
            else:
                # Use regular file reading for smaller files
                with open(str(fname), "r", encoding='utf-8', errors='replace') as f:
                    return f.read()
        except Exception as e:
            if self.io:
                self.io.tool_error(f"Error reading file {fname}: {e}")
            else:
                print(f"Error reading file {fname}: {e}")
            return ""

    def get_tags(self, fname, rel_fname):
        """
        Get tags for a file with caching based on file modification time.
        """
        # Check if the file is in the cache and if the modification time has not changed
        file_mtime = self.get_mtime(fname)
        if file_mtime is None:
            return []
            
        # Create a cache key based on file path and mtime
        cache_key = f"{fname}_{file_mtime}"
        md5_key = hashlib.md5(cache_key.encode()).hexdigest()
        
        # Check cache
        if md5_key in self._tags_cache:
            return self._tags_cache[md5_key]
            
        # Cache miss - process file
        data = list(self.get_tags_raw(fname, rel_fname))
        self._tags_cache[md5_key] = data
        
        return data

    def get_tags_raw(self, fname, rel_fname):
        """
        Extract tags from a file without caching.
        """
        ref_fname_lst = rel_fname.split('/')
        s = deepcopy(self.structure)
        for fname_part in ref_fname_lst:
            if fname_part not in s:
                return
            s = s[fname_part]
        structure_classes = {item['name']: item for item in s['classes']}
        structure_functions = {item['name']: item for item in s['functions']}
        structure_class_methods = dict()
        for cls in s['classes']:
            for item in cls['methods']:
                structure_class_methods[item['name']] = item
        structure_all_funcs = {**structure_functions, **structure_class_methods}

        lang = filename_to_lang(fname)
        if not lang:
            return
        language = get_language(lang)
        parser = get_parser(lang)

        # Load the tags queries
        try:
            scm_fname = """
            (class_definition
            name: (identifier) @name.definition.class) @definition.class

            (function_definition
            name: (identifier) @name.definition.function) @definition.function

            (call
            function: [
                (identifier) @name.reference.call
                (attribute
                    attribute: (identifier) @name.reference.call)
            ]) @reference.call
            """
        except KeyError:
            return

        query_scm = scm_fname

        # Read file content efficiently
        code = self.get_file_content(fname)
        if not code:
            return
            
        # For line references
        codelines = code.split('\n')

        # Hard-coded edge cases
        code = code.replace('\ufeff', '')
        code = code.replace('constants.False', '_False')
        code = code.replace('constants.True', '_True')
        code = code.replace("False", "_False")
        code = code.replace("True", "_True")
        code = code.replace("DOMAIN\\username", "DOMAIN\\\\username")
        code = code.replace("Error, ", "Error as ")
        code = code.replace('Exception, ', 'Exception as ')
        code = code.replace("print ", "yield ")
        pattern = r'except\s+\(([^,]+)\s+as\s+([^)]+)\):'
        # Replace 'as' with ','
        code = re.sub(pattern, r'except (\1, \2):', code)
        code = code.replace("raise AttributeError as aname", "raise AttributeError")

        tree = parser.parse(bytes(code, "utf-8"))
        try:
            tree_ast = ast.parse(code)
        except Exception:
            tree_ast = None

        # Functions from third-party libs or default libs
        try:
            std_funcs, std_libs = self.std_proj_funcs(code, fname)
        except Exception:
            std_funcs, std_libs = [], []
        
        # Functions from builtins
        builtins_funs = [name for name in dir(builtins)]
        builtins_funs += dir(list)
        builtins_funs += dir(dict)
        builtins_funs += dir(set)  
        builtins_funs += dir(str)
        builtins_funs += dir(tuple)

        # Run the tags queries
        query = language.query(query_scm)
        
        captures = query.captures(tree.root_node)
        captures = list(captures)

        saw = set()
        for node, tag in captures:
            if tag.startswith("name.definition."):
                kind = "def"
            elif tag.startswith("name.reference."):
                kind = "ref"
            else:
                continue

            saw.add(kind)
            cur_cdl = codelines[node.start_point[0]]
            category = 'class' if 'class ' in cur_cdl else 'function'
            tag_name = node.text.decode("utf-8")
            
            #  We only want to consider project-dependent functions
            if tag_name in std_funcs:
                continue
            elif tag_name in std_libs:
                continue
            elif tag_name in builtins_funs:
                continue

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
                        info='\n'.join(class_functions), # list unhashable, use string instead
                        references="",
                        line=line_nums,
                    )
                else:
                    # If the class is not in structure_classes, create a basic Tag
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

            yield result

        if "ref" in saw:
            return
        if "def" not in saw:
            return

    def _process_file_for_tags(self, fname, mentioned_fnames, personalize):
        """
        Process a single file and return its tags and personalization info.
        This function is designed to work with multiprocessing.
        """
        personalization = {}
        
        if not Path(fname).is_file():
            if fname not in self.warned_files:
                # Avoid logging from worker processes
                self.warned_files.add(fname)
            return [], personalization
            
        rel_fname = self.get_rel_fname(fname)
        
        if fname in mentioned_fnames:
            personalization[rel_fname] = personalize
        
        # Get tags with caching
        tags = self.get_tags(fname, rel_fname)
        
        return tags, personalization

    def get_ranked_tags(self, other_fnames, mentioned_fnames):
        """
        Multithreaded version of get_ranked_tags that processes files in parallel.
        """
        tags_of_files = []
        personalization = {}
        
        fnames = sorted(set(other_fnames))
        personalize = 10 / len(fnames)
        
        # Determine number of processes - limit to number of CPUs 
        num_processes = min(multiprocessing.cpu_count(), len(fnames))
        
        # Use only multiprocessing for larger repos
        if len(fnames) > 20:
            try:
                # Create process pool
                with multiprocessing.Pool(processes=num_processes) as pool:
                    # Use a manager to handle shared data safely
                    manager = multiprocessing.Manager()
                    shared_warned_files = manager.list(self.warned_files)
                    
                    # Create a partial function with fixed arguments
                    process_file = partial(self._process_file_for_tags, 
                                          mentioned_fnames=mentioned_fnames,
                                          personalize=personalize)
                    
                    # Process all files in parallel and collect results with a progress bar
                    # We use imap to process results as they come in
                    all_results = []
                    for result in tqdm(pool.imap(process_file, fnames), total=len(fnames), desc="Processing files"):
                        all_results.append(result)
                    
                    # Combine results
                    for tags, p_dict in all_results:
                        if tags:
                            tags_of_files.extend(tags)
                        personalization.update(p_dict)
                    
                    # Update warned_files set from the shared list
                    self.warned_files.update(shared_warned_files)
                        
                return tags_of_files
                
            except Exception as e:
                # Fallback to sequential processing if multiprocessing fails
                print(f"Multiprocessing failed, falling back to sequential: {e}")
                pass
                
        # Sequential processing for small repos or as fallback
        for fname in tqdm(fnames, desc="Processing files sequentially"):
            if not Path(fname).is_file():
                if fname not in self.warned_files:
                    if Path(fname).exists():
                        if self.io:
                            self.io.tool_error(f"Code graph can't include {fname}, it is not a normal file")
                        else:
                            print(f"Code graph can't include {fname}, it is not a normal file")
                    else:
                        if self.io:
                            self.io.tool_error(f"Code graph can't include {fname}, it no longer exists")
                        else:
                            print(f"Code graph can't include {fname}, it no longer exists")

                self.warned_files.add(fname)
                continue

            rel_fname = self.get_rel_fname(fname)

            if fname in mentioned_fnames:
                personalization[rel_fname] = personalize
            
            tags = list(self.get_tags(fname, rel_fname))

            if tags is None:
                continue

            tags_of_files.extend(tags)

        return tags_of_files

    def render_tree(self, abs_fname, rel_fname, lois):
        """
        Render a tree representation of a file, with caching.
        """
        key = (rel_fname, tuple(sorted(lois)))

        if key in self.tree_cache:
            return self.tree_cache[key]

        # Read file content
        code = self.get_file_content(abs_fname)
        if not code:
            code = ""

        if not code.endswith("\n"):
            code += "\n"

        context = TreeContext(
            rel_fname,
            code,
            color=False,
            line_number=False,
            child_context=False,
            last_line=False,
            margin=0,
            mark_lois=False,
            loi_pad=0,
            show_top_of_file_parent_scope=False,
        )

        context.add_lines_of_interest(lois)
        context.add_context()
        res = context.format()
        self.tree_cache[key] = res
        return res

    def to_tree(self, tags, chat_rel_fnames):
        if not tags:
            return ""

        tags = [tag for tag in tags if tag[0] not in chat_rel_fnames]
        tags = sorted(tags)

        cur_fname = None
        cur_abs_fname = None
        lois = None
        output = ""

        # Add a bogus tag at the end so we trip the this_fname != cur_fname...
        dummy_tag = (None,)
        for tag in tags + [dummy_tag]:
            this_rel_fname = tag[0]

            # ... here ... to output the final real entry in the list
            if this_rel_fname != cur_fname:
                if lois is not None:
                    output += "\n"
                    output += cur_fname + ":\n"
                    output += self.render_tree(cur_abs_fname, cur_fname, lois)
                    lois = None
                elif cur_fname:
                    output += "\n" + cur_fname + "\n"
                if type(tag) is Tag:
                    lois = []
                    cur_abs_fname = tag.fname
                cur_fname = this_rel_fname

            if lois is not None:
                lois.append(tag.line)

        # Truncate long lines, in case we get minified js or something else crazy
        output = "\n".join([line[:100] for line in output.splitlines()]) + "\n"

        return output

    def find_src_files(self, directory):
        """
        Find all source files in a directory.
        """
        if not os.path.isdir(directory):
            return [directory]

        src_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                src_files.append(os.path.join(root, file))
        return src_files
    
    def find_files(self, dir_list):
        """
        Find Python files in the provided directories using multithreading.
        """
        # Use ThreadPoolExecutor for I/O-bound file search
        all_files = []
        
        with ThreadPoolExecutor(max_workers=min(64, len(dir_list) * 2)) as executor:
            # Submit tasks for each directory
            future_to_dir = {
                executor.submit(self.find_src_files, d): d 
                for d in dir_list if isinstance(d, (str, Path))
            }
            
            # Process results as they complete
            for future in future_to_dir:
                try:
                    files = future.result()
                    all_files.extend(files)
                except Exception as exc:
                    if self.verbose:
                        print(f'Error finding files: {exc}')
        
        # Filter to keep only Python files
        return [item for item in all_files if item.endswith('.py')]


def get_random_color():
    hue = random.random()
    r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(hue, 1, 0.75)]
    res = f"#{r:02x}{g:02x}{b:02x}"
    return res


if __name__ == "__main__":
    # Set up a lock for thread-safe printing
    print_lock = multiprocessing.Lock()
    
    try:
        # Read configuration
        with open('./source/config.yaml', 'r') as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            
        # Use command line argument or default from config
        if len(sys.argv) > 1:
            dir_name = sys.argv[1]
        else:
            dir_name = "/data/veteran/project/TestPlanAgent/test_project/sentry"

        # Extract repository name
        repo_name = dir_name.split(os.path.sep)[-1]
        
        # Initialize the code graph
        code_graph = CodeGraph(root=dir_name, verbose=True)
        
        # Find Python files in the repository
        print("Finding Python files...")
        chat_fnames_new = code_graph.find_files([dir_name])
        print(f"Found {len(chat_fnames_new)} Python files.")

        # Generate tags and graph
        print("Building code graph (this may take some time for large repositories)...")
        tags, G = code_graph.get_code_graph(chat_fnames_new)

        # Print statistics
        print("---------------------------------")
        print(f"🏅 Successfully constructed the code graph for repo directory {dir_name}")
        print(f"   Number of nodes: {len(G.nodes)}")
        print(f"   Number of edges: {len(G.edges)}")
        print("---------------------------------")

        # Save the graph
        output_dir = f'{os.getcwd()}/CKG'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(f'{output_dir}/{repo_name}_graph.pkl', 'wb') as f:
            pickle.dump(G, f)
        
        # Save the tags as JSON lines
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
                })
                f.write(line+'\n')
                
        print(f"🏅 Successfully cached code graph and node tags in directory '{output_dir}'")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)