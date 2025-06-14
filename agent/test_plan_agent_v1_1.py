import re
import sys
from pathlib import Path
import time
import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

import os
import requests
import json
from prompt.test_plan_agent_prompt_v4_5 import PR_TEST_PLAN_EDIT_USER_PROMPT, PR_TEST_PLAN_EDIT_SYSTEM_PROMPT
from utils.tools import Agent_utils
from datetime import datetime




def llm(config, system_prompt, user_prompt):
    # with open('./source/config.yaml', 'r') as f:
    #     config = yaml.load(f, Loader=yaml.FullLoader)

    # api_key = os.environ.get("OPENAI_API_KEY")
    api_key = "sk-wvvB8thiOVcpwJw1i4OI4FqFSItWyC5IePz3hAgrOJ0Jh1MY"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    url = config['Agent']['llm_url'] 
    data = {
        "model": f"{config['Agent']['llm_model']}",  
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    max_retries = 3  # Set the maximum number of retries
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()  
            break
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1: 
                time.sleep(2 ** attempt)  
                continue  
            else:
                raise e 

    response_dict = json.loads(response.text.strip())
    content = response_dict['choices'][0]['message']['content']
    return content

def execute_tool(agent_utils, tool_name, tool_param):
    
    observation = ''
    if tool_name == 'search_class_in_project' or tool_name == 'search_function_in_project':
        entity_type = tool_name.split('_')[1]
        observation = agent_utils.search_entity_in_project(tool_param[f"{entity_type}_name"])

    elif tool_name == 'search_code_dependencies':
        observation = agent_utils.search_code_dependencies(tool_param['entity_name'])

    elif tool_name == 'search_files_path_by_pattern':
        observation = agent_utils.search_files_path_by_pattern(tool_param['pattern'])

    elif tool_name == 'view_file_contents':
        file_path = tool_param.get('file_path')
        index = tool_param.get('index', 0)
        start_line = tool_name.get('start_line', None)
        end_line = tool_name.get('end_line', None)
        observation = agent_utils.view_file_contents(file_path, index, start_line, end_line)

    elif tool_name == 'view_code_changes':
        observation = agent_utils.view_code_changes(tool_param['file_path'])
    
    elif tool_name == 'explore_project_structure':
        root_path = tool_param.get("root_path", "/")
        max_depth = tool_param.get("max_depth", 3)
        include_patterns = tool_param.get("include_patterns", None)
        exclude_patterns = tool_param.get("exclude_patterns", None)
        observation = agent_utils.explore_project_structure(root_path, max_depth, include_patterns, exclude_patterns)

    observation = json.dumps(observation)
    return observation

def agent(config_path):
    with open(config_path, 'r') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    agent_utils = Agent_utils(config)
    reformat_pr_info = agent_utils.reformat_pr_info_for_user_prompt()
    PR_Content = reformat_pr_info['PR_Content'] 
    PR_Changed_Files = reformat_pr_info['PR_Changed_Files']

    user_prompt = PR_TEST_PLAN_EDIT_USER_PROMPT.format(
        PR_Project_Root_Dir=config['CKG']['project_dir'],
        PR_Content=PR_Content,
        PR_Changed_Files=PR_Changed_Files
    ) + '\n'
    test_plan = ""
    for i in range(1, 20):
        session_message = ''
        content = llm(config, PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, user_prompt)
        if 'Test Plan Details' in content:
            thought_content = ''.join(content.split('Thought')[1].split('Test Plan Details')[0].split(':')[1:]).replace('#', '').strip()
            print('Test Plan completed!')
            session_message = f"Thought {i}: " + thought_content + '\n'
            test_plan = '\n'.join(content.split('Test Plan Details')[1].splitlines()[1:]).replace('```', '').strip()
            session_message += f"Test Plan: \n" + test_plan + '\n'
            user_prompt += session_message
            break
        else:
            thought_content = ''.join(content.split('Thought')[1].split('Action')[0].split(':')[1:]).replace('#', '').strip()
            action_name = content.split('Action')[1].splitlines()[1].replace('```','').strip()
            action_param = json.loads(''.join(content.split('Action')[1].splitlines()[2:]).replace('```', ''))
        if action_name == '' or thought_content == '' or action_param == None:
            print("Some things are empty, please check")
            print(content + '\n')
            print(f"Thought {i}: " + thought_content + '\n' + f"Action {i}: " + action_name + '\n' + json.dumps(action_param) +'\n')
            break
        observation = execute_tool(agent_utils, action_name, action_param)
        session_message = f"Thought {i}: " + thought_content + '\n' + f"Action {i}: " + action_name + '\n' + json.dumps(action_param) + '\n' + f"Observation {i}: " + observation + '\n'
        user_prompt += session_message
        print(f"Round {i}\n")
        print(session_message)
        print("--------------------------------------\n")
    # 获取当前时间并格式化为字符串
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config['Agent']['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, f"{config['Agent']['llm_model']}_{current_time}.txt")
    # 使用当前时间作为文件名的一部分
    with open(output_file_path, 'w') as f:
        f.write(user_prompt)

    return test_plan
def main():
    agent('./source/config.yaml')

if __name__ == "__main__":
    main()