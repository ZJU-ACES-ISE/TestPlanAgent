import base64
import json
import pickle
import re
import typing as t
import ast
import requests
import os
import glob
from composio import action

import sys
from pathlib import Path

import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

with open('./source/config.yaml', 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

DIFF_URL = config['agent']['diff_url']
PR_URL = "https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"

token = "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"

headers = {
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github.v3+json',
}

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
def Get_PR_NL_Content(owner: str, repo: str, pull_number: str, thought: str) -> t.Dict:
    """
    Get description and title for a github PR.

    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param pull_number: Pull request number to retrive the diff for.
    :param thought: Thought to be used for the request.

    :return pr_nl_content: Description and title for give pull request.
    """

    body = None
    title = None
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        body = str(data['body'])
        title = str(data['title'])
    return {
            "title": title,
            "description": body
        }
        

@action(toolname="github")
def Parse_PR_and_Remove_Test_Plan(pr_nl_content: str, thought: str) -> t.Dict:
    """
    Parse PR and remove test plan

    :param pr_nl_content: Description and title for give pull request.
    :param thought: Thought to be used for the request.

    :return handled_pr: Handled_pr includes test plan and pr without test plan.
    """

    result = llm_restructure_pr_body(pr_nl_content)

    dict_result = json.loads(result)

    handled_pr = {
        "pr_without_test_plan": dict_result["Description of changes"],
        "test_plan": dict_result["Test plan"],
        "ori_pr" : pr_nl_content
    }
    return handled_pr

@action(toolname="github")
def GITHUB_GET_Files_And_Get_Func(owner: str, repo: str, pull_number: str, thought: str) -> t.Dict:
    """
    Get the code files changed in pr and get the function name where the code has been changed.

    :param owner: Name of the owner of the repository.
    :param repo: Name of the repository.
    :param pull_number: Pull request number to retrive the diff for.
    :param thought: Thought to be used for the request.

    :return pr_total_changes: Pr_total_changed_functions includes the function names of all codes that have changed under the current pr. Pr_total_changed_codes includes the code patches of all codes that have changed under the current pr.
    """

    # 获取完整代码及变更代码
    files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/files"
    response = requests.get(files_url, headers=headers)
    pr_total_changed_functions = []
    pr_total_changed_codes = {}
    if response.status_code == 200:
        data = response.json()
        for file in data:
            if file['filename'].endswith('.py'):
                full_code_url = file['contents_url']
                original_code = None
                patch = None
                if full_code_url:
                    response = requests.get(full_code_url, headers=headers)
                    file_content = response.json()['content']
                    original_code = base64.b64decode(file_content).decode('utf-8')
                    
                if 'patch' in file:
                    patch = file['patch']
                    pr_total_changed_codes[file['filename']] = patch

                changed_functions = extract_function_code_from_patch(original_code, patch)
                pr_total_changed_functions += changed_functions
    pr_total_changes = {
        "pr_total_changed_functions": pr_total_changed_functions,
        "pr_total_changed_codes": pr_total_changed_codes
    }
    return pr_total_changes

@action(toolname="github")
def Change_Type_Classification(pr_nl_content: str, pr_total_changed_codes: str, thought: str) -> str:
    """
    Code change type determination: application feature or foundational feature.

    :param pr_nl_content: PR Natural Language Content.
    :param pr_total_changed_codes: Pr_total_changed_codes includes the code patches of all codes that have changed under the current pr
    :param thought: Thought to be used for the request.

    :return change_type: Change type of the PR.
    """

    prompt = f"""
    Based on the following pull request (PR) details, determine the type of change. 
    Classify the change as either "application feature" or "foundational feature" based on the context provided.
    
    PR Description: {pr_nl_content}
    
    PR Code Change: {pr_total_changed_codes}
    
    No reasoning process is required, and classification results need to be output urgently, the classification should be in the format: 
    {{'change_type': 'application feature' or 'foundational feature'}}.
    """

    response = ask_for_llm(prompt)
    
    response_dict = json.loads(response.text.strip())
    
    change_type = response_dict['choices'][0]['message']['content']

    return change_type

@action(toolname="github")
def Change_Impact_Scope_Determination(pr_total_changed_functions: str, thought: str) -> str:
    """
    Change impact scope determination.

    :param pr_total_changed_functions: Pr_total_changed_functions includes the function names of all codes that have changed under the current pr.
    :param thought: Thought to be used for the request.

    :return recently_affected_function: Recently affected function.
    """
    pr_total_changed_functions = ast.literal_eval(pr_total_changed_functions)
    
    affected_functions_list = []

    # 有项（无环）图 多节点最近祖先求解
    recently_affected_function = "function_name"
    return recently_affected_function

@action(toolname="github")
def Test_Plan_Generator(change_type: str, pr_nl_content: str, pr_total_changed_functions: str, pr_total_changed_codes: str, recently_affected_function: str, thought: str) -> str:

    """
    Test plan generator.
    
    :param change_type: Change type of the PR.
    :param pr_nl_content: PR Natural Language Content.
    :param pr_total_changed_functions: Pr_total_changed_functions includes the function names of all codes that have changed under the current pr.
    :param pr_total_changed_codes: Pr_total_changed_codes includes all the changed code snippets of the current pr.
    :param recently_affected_function: Recently affected function.
    :param thought: Thought to be used for the request.

    :return test_plan : Test plan.
    """

    test_plan = None

    if "application feature" in change_type:
        test_plan = Test_Plan_Generator_for_application_feature(pr_nl_content, pr_total_changed_codes, recently_affected_function)
    elif "foundational feature" in change_type:
        test_plan = Test_Plan_Generator_for_foundational_feature(pr_nl_content, pr_total_changed_codes, pr_total_changed_functions)

    return test_plan
def Test_Plan_Generator_for_foundational_feature(pr_nl_content, pr_total_changed_codes, pr_total_changed_functions):
    """
    为基础型功能生成测试计划
    """
    prompt = f"""
    You are a software engineer responsible for generating a comprehensive test plan for a GitHub pull request (PR). 
    Your task is to draft a test plan based on the PR's natural language content, changed code snippets and changed functions.

    A test plan is used to verify that the current PR functions as expected. 
    This PR involves foundational feature changes, which typically require unit tests to validate the changes. 

    Please check whether `pr_total_changed_codes` includes unit tests for the modified functions:
    - If unit tests are present, provide a test plan by describing the process to run those unit tests to verify the PR.
    - If unit tests are missing for any of the changed functions, list those functions and propose appropriate unit tests for them, in addition to describing how to run the available unit tests.

    Here are the details of the pull request:

    PR Description: {pr_nl_content}
    PR Code Changes: {pr_total_changed_codes}
    PR Changed Functions: {pr_total_changed_functions}

    """

    response = ask_for_llm(prompt)

    response_dict = json.loads(response.text.strip())

    test_plan = response_dict['choices'][0]['message']['content']

    processed_string = re.sub(r'\n+', '\n', test_plan)  # 替换多余的换行符为单一换行符

    # 保存到 markdown 文件
    with open('./log/4o_test_plan_good_1.md', 'w', encoding='utf-8') as file:
        file.write(processed_string)

    return test_plan

def get_function_details(source_code):
    """
    使用 AST 解析源代码，提取函数名称、起始行号和结束行号
    """
    tree = ast.parse(source_code)
    function_details = []
    
    # 遍历所有的函数定义
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # 获取函数名称、起始行号、结束行号
            function_details.append({
                'name': node.name,
                'start_line': node.lineno,
                'end_line': node.end_lineno  # 获取函数的结束行号
            })
    
    return function_details

def extract_function_code_from_patch(original_code, patch):
    # 获取原始函数列表
    original_functions = get_function_details(original_code)

    patch_lines = patch.splitlines()
    
    # 提取修改行号
    modified_lines = set()
    for line in patch_lines:
        match = re.search(r'@@\s*([\s\S]+?)\s*@@', line)
        if match:
            # 提取修改的行号范围（以 @@ -10,7 +10,7 @@ 为例）
            data_between_at = match.group(1)
            parts = data_between_at.split(' ')
            old_range = parts[0][1:].split(',')
            new_range = parts[1][1:].split(',')
            modified_lines.update(range(int(old_range[0]), int(old_range[0]) + int(old_range[1]) + 1))
            modified_lines.update(range(int(new_range[0]), int(new_range[0]) + int(new_range[1]) + 1))

    # 检查哪些函数被修改
    changed_functions = []
    for function in original_functions:
        # 获取函数的起始行号和结束行号
        func_start = function['start_line']
        func_end = function['end_line']
        
        # 判断修改的行号是否与函数的行号范围有重叠
        if any(func_start <= line <= func_end for line in modified_lines):
            changed_functions.append(function['name'])

    return changed_functions

def ask_for_llm(prompt):
    # api_key = os.environ.get("OPENAI_API_KEY")
    api_key = "sk-vhd396de43bb46de996a85f47f3be8579fe14ce8d49ZYSk3"
    url = "https://api.gptsapi.net/v1/chat/completions"  # 自定义的base URL
    # url = "https://api.deepseek.com/v1/chat/completions"  # 自定义的base URL

    # 定义请求体
    data = {
        "model": "gpt-4o",  
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

    return response