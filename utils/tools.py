import base64
import json
import re
import typing as t

import requests

from composio import action
from data_process.llm_process_3 import llm_restructure_pr_body, 

DIFF_URL = "https://github.com/{owner}/{repo}/pull/{pull_number}.diff"
PR_URL = "https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"


class DiffFormatter:
    def __init__(self, diff_text):
        self.diff_text = diff_text
        self.formatted_files = []

    def parse_and_format(self):
        """Parse the diff and return a structured format suitable for an AI review agent."""
        current_file = None
        current_chunk = None
        lines = self.diff_text.split("\n")

        for line in lines:
            # New file
            if line.startswith("diff --git"):
                if current_file:
                    self.formatted_files.append(current_file)
                current_file = {
                    "file_path": self._extract_file_path(line),
                    "chunks": [],
                }

            # File metadata (index, mode changes etc)
            elif (
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


@action(toolname="github")
def get_pr_diff(owner: str, repo: str, pull_number: str, thought: str) -> str:
    """
    Get .diff data for a github PR.

    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param pull_number: Pull request number to retrive the diff for.
    :param thought: Thought to be used for the request.

    :return diff: .diff content for give pull request.
    """
    diff_text = requests.get(
        DIFF_URL.format(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
        )
    ).text
    return DiffFormatter(diff_text).parse_and_format()


@action(toolname="github")
def get_pr_metadata(owner: str, repo: str, pull_number: str, thought: str) -> t.Dict:
    """
    Get metadata for a github PR.

    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param pull_number: Pull request number to retrive the diff for.
    :param thought: Thought to be used for the request.

    :return metadata: Metadata for give pull request.
    """

    data = requests.get(
        PR_URL.format(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
        )
    ).json()

    response = {
        "title": data["title"],
        "comments": data["comments"],
        "commits": data["commits"],
        "additions": data["additions"],
        "deletions": data["deletions"],
        "changed_files": data["changed_files"],
        "head": {
            "ref": data["head"]["ref"],
            "sha": data["head"]["sha"],
        },
        "base": {
            "ref": data["base"]["ref"],
            "sha": data["base"]["sha"],
        },
    }
    return response

@action(toolname="github")
def Parse_PR_and_Remove_Test_Plan(pr_nl_content: str, thought: str) -> t.Dict:
    """
    Parse PR and remove test plan

    :param pr_nl_content: PR Natural Language Content.

    :return handled_pr: Handled_pr includes test plan and pr without test plan.
    """

    result = llm_restructure_pr_body(pr_nl_content)

    handled_pr = {
        "pr_without_test_plan": result["Description of changes"],
        "test_plan": result["Test plan"],
        "ori_pr" : pr_nl_content
    }
    return handled_pr

@action(toolname="github")
def GITHUB_GET_Files(owner: str, repo: str, pull_number: str, thought: str) -> t.Dict:
    """
    Get the code files changed in pr.

    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param pull_number: Pull request number to retrive the diff for.
    :param thought: Thought to be used for the request.

    :return pr_code_files: Pr_code_files contains code additions and deletions for all changed files.
    """
    token = "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"

    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    pr_code_files = {}
    # 获取完整代码及变更代码
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/files"
    response = requests.get(files_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        for file in data:
            if file['filename'].endswith('.py'):
                full_code_url = file['contents_url']
                if full_code_url:
                    response = requests.get(full_code_url, headers=headers)
                    file_content = response.json()['content']
                    all_code = base64.b64decode(file_content).decode('utf-8')
                    pr_code_files[file['filename']]["完整代码"] = all_code
                    
                if 'patch' in file:
                    patch = file['patch']
                    pr_code_files[file['filename']]["变更代码"] = patch

    return pr_code_files

@action(toolname="github")
def Code_Analysis_And_Get_Func(pr_code_files: str) -> t.Dict:
    """
    Analysis code files and get the function level code.

    :param pr_code_files: Pr_code_files contains code additions and deletions for all changed files.

    :pr_function_level_code: Pr_function_level_code contains the additions and deletions of function-level code.
    """

    # 序列化pr_code_files
    dict_pr_code_files = json.loads(pr_code_files)
    
    # 获取函数级代码
    pr_function_level_code = {}

    for file_name in dict_pr_code_files:
        if '变更代码' in dict_pr_code_files[file_name]:
            patch = dict_pr_code_files[file_name]['变更代码']
            function_level_code = extract_function_code_from_patch(patch)
            pr_function_level_code[file_name] = function_level_code

    return pr_function_level_code

@action(toolname="github")
def Change_Type_Classification(pr_nl_content: str, pr_function_level_code: str) -> t.Dict:
    """
    Code change type determination: application function/basic function.

    :param pr_nl_content: PR Natural Language Content.
    :param pr_function_level_code: Pr_function_level_code contains the additions and deletions of function-level code.

    :return change_type: Change type of the PR.
    """

    prompt = f"""
    Based on the following pull request (PR) details, determine the type of change. 
    Classify the change as either "application function" or "basic function" based on the context provided.
    
    PR Description: {pr_nl_content}
    
    PR Code Change: {pr_function_level_code}
    
    The classification should be in the format {{'change_type': 'application function' or 'basic function'}}.
    """

    # api_key = os.environ.get("OPENAI_API_KEY")
    api_key = "sk-bdb2caae8edf4fc1a809919a192074b3"
    # url = "https://api.gptsapi.net/v1/chat/completions"  # 自定义的base URL
    url = "https://api.deepseek.com/v1/chat/completions"  # 自定义的base URL

    # 定义请求体
    data = {
        "model": "deepseek-chat",  
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    # 设置头部
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 发起请求
    response = requests.post(url, json=data, headers=headers)
    
    response_dict = json.loads(response.text.strip())
    
    change_type = {"change_type": response_dict['choices'][0]['message']['content']}

    return change_type

@action(toolname="github")
def Change_Impact_Scope_Determination(pr_function_level_code: str) -> str:
    """
    Change impact scope determination.

    :param pr_function_level_code: Pr_function_level_code contains the additions and deletions of function-level code.

    :return recently_affected_function: Recently affected function.
    """
    dict_pr_function_level_code = json.loads(pr_function_level_code)
    
    affected_functions_list = []

    for file_name in dict_pr_function_level_code:
        for function_name in dict_pr_function_level_code[file_name]:
            affected_functions_list.append(function_name)
    # 有项（无环）图 多节点最近祖先求解

    return "function"

@action(toolname="github")
def Test_Plan_Generator() -> str:
    """
    Test plan generator.

    :return test_plan : .
    """
    return 1


def extract_function_code_from_patch(patch):
    """
    从Git diff的patch字符串中提取每个函数的代码段。
    :param patch: Git diff字符串
    :return: 一个字典，包含每个函数的代码段
    """
    # 正则表达式，用来匹配Python函数定义
    function_pattern = re.compile(r"def\s+(\w+)\s*\(.*\)\s*:", re.M)
    
    # 解析patch内容并提取出增改的代码行
    lines = patch.splitlines()
    
    # 用来存储最终结果
    function_code = {}
    
    current_function = None
    current_code = []
    
    for line in lines:
        # 如果是函数定义，开始提取代码
        function_match = function_pattern.match(line)
        if function_match:
            # 如果已经有函数正在收集代码，则存储它
            if current_function:
                function_code[current_function] = "\n".join(current_code)
            
            # 更新当前函数的名称，并开始收集代码
            current_function = function_match.group(1)
            current_code = [line]  # 将当前的函数定义行作为代码的一部分
        elif current_function:
            # 如果已经在收集函数代码，并且这行是函数内部的代码，继续添加到当前代码中
            current_code.append(line)
    
    # 最后存储最后一个函数的代码
    if current_function:
        function_code[current_function] = "\n".join(current_code)
    
    return function_code