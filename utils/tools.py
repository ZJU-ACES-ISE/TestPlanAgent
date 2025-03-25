import pickle
import typing as t
import requests
import os
import glob
import os
import fnmatch
import json
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

from data_process.llm_process_3 import llm_restructure_pr_body
# DIFF_URL = "https://github.com/{owner}/{repo}/pull/{pull_number}.diff"

class Agent_utils:

    def __init__(self, config):
        self.config = config
        self.DIFF_URL = self.config['Agent']['diff_url']

        self.token = "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"

        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
        }
    
    class DiffFormatter:
        def __init__(self, diff_text, current_file):
            self.diff_text = diff_text
            self.formatted_files = []
            self.current_file = current_file

        def parse_and_format(self):
            """Parse the diff and return a structured format suitable for an AI review agent."""

            current_chunk = None
            lines = self.diff_text.split("\n")

            current_file = {
                "file_path": self.current_file,
                "chunks": [],
            }

            if current_file:
                self.formatted_files.append(current_file)
    
            for line in lines:
                # New file
                # if line.startswith("diff --git"):
                #     if current_file:
                #         self.formatted_files.append(current_file)
                #     current_file = {
                #         "file_path": self._extract_file_path(line),
                #         "chunks": [],
                #     }

                # File metadata (index, mode changes etc)
                if (
                    line.startswith("index ")
                    or line.startswith("new file")
                    or line.startswith("deleted file")
                ):
                    if current_file:
                        current_file["metadata"] = line

                # Chunk header
                elif line.startswith("@@"):
                    if current_file:
                        current_chunk = self._parse_chunk_header(line)
                        current_file["chunks"].append(current_chunk)

                # Content lines
                elif current_chunk is not None and current_file is not None:
                    if line.startswith("+"):
                        current_chunk["changes"].append(
                            {
                                "type": "addition",
                                "content": line[1:],
                                "new_line_number": current_chunk["new_line"],
                            }
                        )
                        current_chunk["new_line"] += 1
                    elif line.startswith("-"):
                        current_chunk["changes"].append(
                            {
                                "type": "deletion",
                                "content": line[1:],
                                "old_line_number": current_chunk["old_line"],
                            }
                        )
                        current_chunk["old_line"] += 1
                    elif line.startswith("\\"):
                        # Handle "No newline at end of file" cases
                        continue
                    else:  # Context line
                        current_chunk["changes"].append(
                            {
                                "type": "context",
                                "content": line[1:] if line.startswith(" ") else line,
                                "old_line_number": current_chunk["old_line"],
                                "new_line_number": current_chunk["new_line"],
                            }
                        )
                        current_chunk["old_line"] += 1
                        current_chunk["new_line"] += 1

            if current_file:
                self.formatted_files.append(current_file)

            return self.format_for_agent()

        def _extract_file_path(self, diff_header):
            """Extract the file path from diff header line."""
            parts = diff_header.split(" ")
            return parts[-1].lstrip("a/").lstrip("b/")

        def _parse_chunk_header(self, header):
            """Parse the @@ line to get the line numbers."""
            # Example: @@ -1,7 +1,6 @@
            parts = header.split(" ")
            old_start = int(parts[1].split(",")[0].lstrip("-"))
            new_start = int(parts[2].split(",")[0].lstrip("+"))

            return {
                "header": header,
                "old_start": old_start,
                "new_start": new_start,
                "old_line": old_start,
                "new_line": new_start,
                "changes": [],
            }

        def format_for_agent(self):
            """Format the parsed diff in a clear, AI-friendly format."""
            formatted_output = []

            for file in self.formatted_files:
                file_info = f"\nFile: {file['file_path']}\n"
                if "metadata" in file:
                    file_info += f"Metadata: {file['metadata']}\n"
                formatted_output.append(file_info)

                for chunk in file["chunks"]:
                    formatted_output.append(f"\nChunk {chunk['header']}")
                    max_line_number_length = max(
                        [
                            len(str(change["new_line_number"]))
                            for change in chunk["changes"]
                            if change["type"] != "deletion"
                        ]
                    )
                    for change in chunk["changes"]:
                        if change["type"] == "addition":
                            line_info = f"+ {change['new_line_number']}"
                            line_info = line_info.rjust(max_line_number_length + 2)
                        elif change["type"] == "deletion":
                            line_info = " "
                            line_info = "-" + line_info.rjust(max_line_number_length + 1)
                        else:
                            line_info = f" {change['new_line_number']}"
                            line_info = line_info.rjust(max_line_number_length + 2)
                        # spaces = ' ' * (15 - len(line_info))
                        spaces = ""
                        formatted_output.append(f"{line_info}{spaces}: {change['content']}")

            return "\n".join(formatted_output)

        def get_structured_diff(self):
            """Return the structured diff data for programmatic use."""
            return self.formatted_files

    def search_entity_in_project(self, entity_name: str) -> t.Dict:

        """
        Search for information about an entity (class or function) from the code knowledge graph. The entity information includes entity name, entity type, file to which it belongs, and number of lines in the file.

        :param entity_name: The name of the entity (class or function) to be queried.
        :param thought: Thought to be used for the request.

        :return entity_detail: The entity detail includes entity name, entity type, file to which it belongs, and number of lines in the file.
        """
        with open(f"{self.config['CKG']['graph_pkl_dir']}", 'rb') as f:
            CKG = pickle.load(f)
        
        if entity_name in CKG:
            # 获取节点的属性
            node_attributes = CKG.nodes[entity_name]
            node_attributes.pop('references')
            # print(f"节点 {entity_name} 的属性：", node_attributes)
            return json.dumps({"detail_of_entity": node_attributes})

        return "cat not find the entity (class or function) in the project"

    def search_code_dependencies(self, entity_name: str) -> t.Dict: 
        """
        Searches for entities that points to an entity or to which an entity points.

        :param entity_name: Entity name to search.
        :param in_or_out: `in` means searching for other entities pointing to this entity, and `out` means searching for other entities pointed to by this entity.
        :param thought: Thought to be used for the request.

        :return neighbors: Neighbors of the entity.
        """
        
        with open(f"{self.config['CKG']['graph_pkl_dir']}", 'rb') as f:
            CKG = pickle.load(f)

        neighbors = {}
        if entity_name in CKG:
            neighbors['entities_that_CALL_the_target_entity'] = list(CKG.predecessors(entity_name))
            neighbors['entities_CALLED_by_the_target_entity'] = list(CKG.neighbors(entity_name))
            return json.dumps(neighbors)

        return 'cat not find the entity in code knowledge graph'

    def search_files_path_by_pattern(self, pattern):
        cur_work_dir = os.getcwd()

        if not os.path.isabs(pattern):
            pattern = os.path.join(cur_work_dir, '**', pattern)
        
        matched_pattern = glob.glob(pattern, recursive=True)

        path_list = [{"path": file} for file in matched_pattern]

        return json.dumps(path_list)

    def view_file_contents(self, file_path, index=0, start_line=None, end_line=None):
        if os.path.isdir(file_path):
            return "The provided path is a directory, not a file."
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                if start_line is not None and end_line is not None:
                    start_idx = max(0, start_line - 1)
                    all_lines = file.readlines()
                    end_idx = min(end_line, len(all_lines))
                    file_content = ''.join(all_lines[start_idx:end_idx])
                    return json.dumps({"file_content": file_content})
                else:
                    lines_per_chunk = 100
                    start_idx = index * lines_per_chunk
                    all_lines = file.readlines()
                    end_idx = min(start_idx + lines_per_chunk, len(all_lines))
                    
                    if start_idx >= len(all_lines):
                        return f"Index out of range. File has {len(all_lines)} lines."
                    file_content = ''.join(all_lines[start_idx:end_idx])
                    return json.dumps({"file_content": file_content})
        except FileNotFoundError:
            return f"File not found: {file_path}"
        except PermissionError:
            return f"Permission denied: {file_path}"
        except UnicodeDecodeError:
            return f"Unable to decode file: {file_path}. The file may be binary or use an unsupported encoding."
        except Exception as e:
            return f"An error occurred: {e}. A valid absolute file path is required."

    def view_code_changes(self, file_path):
        diff_list = json.loads(requests.get(self.DIFF_URL).text)
        for diff in diff_list:
            if diff['filename'] == file_path:
                patch = diff['patch']
                formatted_patch = self.DiffFormatter(patch, file_path).parse_and_format()
                return json.dumps({'code_changes': formatted_patch})
        return 'File not found in diff list. A path relative to the repo root is required.'

    def reformat_pr_info_for_user_prompt(self):
        body = None
        title = None
        PR_url = self.config['Agent']['PR_url']
        response = requests.get(PR_url, headers=self.headers)
        if response.status_code == 200:
            data = response.json()
            body = data['body']
            title = data['title']

        result = llm_restructure_pr_body(body).replace('```', '').replace('json','')
        dict_result = json.loads(result)
        dict_result["Description of changes"] = title + '\n' + dict_result["Description of changes"] 

        PR_Files_url = PR_url + '/files'
        response = requests.get(PR_Files_url, headers=self.headers)

        if response.status_code == 200:
            PR_Changed_Files = response.json()
            for file in PR_Changed_Files:
                file.pop('sha', None)
                file.pop('blob_url', None)
                file.pop('raw_url', None)
                file.pop('contents_url', None)
                file.pop('patch', None)
        tmp_dir = self.config['Judge']['tmp_dir']
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, "PR_body.json")
        with open(f"{tmp_path}", 'w') as f:
            json.dump(dict_result, f)

        return {'PR_Content': dict_result["Description of changes"], 'PR_Changed_Files': PR_Changed_Files, 'Test_Plan': dict_result["Test plan"]}

    def explore_project_structure(
        self, 
        root_path: str, 
        max_depth: int = 3, 
        include_patterns: Optional[List[str]] = None, 
        exclude_patterns: Optional[List[str]] = None,
    ) -> str:
        """
        Explore and return the project file structure as either JSON or a formatted tree.
        
        Args:
            root_path (str): The starting directory path to explore
            max_depth (int, optional): Maximum depth of directories to display. Defaults to 3.
            include_patterns (List[str], optional): List of patterns to include. Defaults to None.
            exclude_patterns (List[str], optional): List of patterns to exclude. Defaults to None.
        
        Returns:
            str: Project structure in the requested format or error message
        """
        if not os.path.exists(root_path):
            return f"Error: Path '{root_path}' does not exist."
        
        if not os.path.isdir(root_path):
            return f"Error: Path '{root_path}' is not a directory."
        
        if include_patterns is None:
            include_patterns = ["*"]  
        
        if exclude_patterns is None:
            exclude_patterns = []  
        
        def should_include(path: str) -> bool:
            """Determine if a path should be included based on patterns."""
            filename = os.path.basename(path)
            
            for pattern in exclude_patterns:
                if os.path.sep in pattern: 
                    if fnmatch.fnmatch(path, pattern):
                        return False
                if fnmatch.fnmatch(filename, pattern):
                    return False
                
            if os.path.isdir(path) and not any(os.path.sep in p for p in include_patterns):
                return True
                
            for pattern in include_patterns:
                if os.path.sep in pattern:  
                    if fnmatch.fnmatch(path, pattern):
                        return True
                elif fnmatch.fnmatch(filename, pattern):
                    return True
                    
            return False
        
        # Generate JSON format structure
        def generate_json_structure() -> str:
            """Generate directory structure in JSON format."""
            def build_structure(dir_path: str, current_depth: int = 0) -> Dict[str, Any]:
                """Recursively build a dictionary representing the directory structure."""
                name = os.path.basename(dir_path)
                result = {
                    "name": name if name else dir_path,  # Handle root directory
                    "type": "directory",
                    "path": dir_path,
                    "children": []
                }
                
                if current_depth > max_depth:
                    result["note"] = "max depth reached"
                    return result
                    
                try:
                    entries = os.listdir(dir_path)
                    
                    # Sort entries: directories first, then files
                    dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e)) 
                            and should_include(os.path.join(dir_path, e))]
                    files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e)) 
                            and should_include(os.path.join(dir_path, e))]
                    
                    dirs.sort()
                    files.sort()
                    
                    # Process directories
                    for d in dirs:
                        path = os.path.join(dir_path, d)
                        child = build_structure(path, current_depth + 1)
                        result["children"].append(child)
                    
                    # Process files
                    for f in files:
                        path = os.path.join(dir_path, f)
                        file_info = {
                            "name": f,
                            "type": "file",
                            "path": path
                        }
                        result["children"].append(file_info)
                        
                except PermissionError:
                    result["error"] = "Permission denied"
                except Exception as e:
                    result["error"] = str(e)
                    
                return result
                
            # Build the structure starting from root_path
            structure = build_structure(root_path)
            return json.dumps(structure, indent=2)

        return generate_json_structure()

def main():
    root_path = "/home/veteran/projects/multiAgent/TestPlanAgent/test_projects/opentrons/README.md"
    print()

if __name__ == '__main__':
    main()