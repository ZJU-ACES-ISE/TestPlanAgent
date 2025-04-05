import re
import sys
from pathlib import Path
import time
import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

import os
import requests
import json
import threading
from prompt.tot.test_plan import PR_TEST_PLAN_EDIT_USER_PROMPT, PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, RELEVANCE_EVALUATION_PROMPT, PR_TEST_PLAN_EDIT_PROMPT
from utils.tools import Agent_utils
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Define the helper function for processing individual ReAct pairs
def process_react_pair(react, config, agent_utils, PR_Content, PR_Changed_Files, RELEVANCE_EVALUATION_PROMPT):
    """Process a single ReAct pair in a separate thread."""
    thought = react['thought']
    action_name = react['action_name']
    action_param = react['action_parameters']
    
    # Execute the tool
    try:
        observation = execute_tool(agent_utils, action_name, action_param)
    except Exception as e:
        observation = str(e)
    
    # Create the relevance evaluation prompt
    evaluate_ReAct_relevance_prompt = RELEVANCE_EVALUATION_PROMPT.format(
        PR_Content=PR_Content,
        PR_Changed_Files=PR_Changed_Files,
        Thought=thought,
        Action_Name=action_name,
        Action_Parameters=json.dumps(action_param),
        Action_Observation=observation
    )
    
    # Evaluate the relevance
    relevance = evaluate_ReAct_relevance(config, evaluate_ReAct_relevance_prompt)
    
    # Return the results
    return {
        'observation': observation,
        'relevance': relevance['score'],
        'justification': relevance['justification']
    }

def extract_relevance_evaluation(response_text):
    score_pattern = r'Relevance Score:\s*(\d+(?:\.\d+)?)'
    justification_pattern = r'Justification:\s*(.*?)(?:\n\n|\Z)'
    
    score_match = re.search(score_pattern, response_text)
    score = None
    if score_match:
        try:
            score = float(score_match.group(1))
            if score.is_integer():
                score = int(score)
        except ValueError:
            print(f"Error: Relevance score '{score_match.group(1)}' is not a valid number.")
            score = 0
    else:
        print("Error: Relevance score not found.")
        score = 0
    
    justification_match = re.search(justification_pattern, response_text, re.DOTALL)
    justification = justification_match.group(1).strip() if justification_match else None
    
    return {
        "score": score,
        "justification": justification
    }

def extract_thought_action_pairs(text):
    thought_pattern = r'\*\*Thought\*\*: (.*?)\n'
    action_name_pattern = r'```(.*?)\n'
    action_params_pattern = r'```.*?\n(.*?)```'
    expected_info_pattern = r'\*\*Expected Information\*\*: (.*?)\n'
    
    pair_pattern = r'#### Thought-Action Pair (TA\d+)(.*?)(?=#### Thought-Action Pair TA\d+|\Z)'
    pairs = re.findall(pair_pattern, text, re.DOTALL)
    
    results = []
    
    for pair_id, pair_content in pairs:
        thought_match = re.search(thought_pattern, pair_content)
        action_name_match = re.search(action_name_pattern, pair_content)
        action_params_match = re.search(action_params_pattern, pair_content, re.DOTALL)
        expected_info_match = re.search(expected_info_pattern, pair_content)
        
        if thought_match and action_name_match and action_params_match and expected_info_match:
            try:
                action_params_json = json.loads(action_params_match.group(1).strip())
            except json.JSONDecodeError:
                action_params_json = "Invalid JSON"
            
            pair_dict = {
                "id": pair_id.strip(),
                "thought": thought_match.group(1).strip(),
                "action_name": action_name_match.group(1).strip(),
                "action_parameters": action_params_json,
                "expected_information": expected_info_match.group(1).strip()
            }
            
            results.append(pair_dict)
    
    return results

def evaluate_ReAct_relevance(config, system_prompt, user_prompt=""):
    content = llm(config, system_prompt, user_prompt)
    
    relevance_evaluation = extract_relevance_evaluation(content)
    return relevance_evaluation

def llm(config, system_prompt, user_prompt):
    # with open('./source/config.yaml', 'r') as f:
    #     config = yaml.load(f, Loader=yaml.FullLoader)

    # api_key = os.environ.get("OPENAI_API_KEY")
    api_key = config['Agent']['api_key']
    # api_key = "sk-Y9Ba7ca3cb6235a6b6f2d371c3bc11db13f0a1e8bf9a4p5o"
    # api_key = "sk-6072ffbc181542f2862a1fd04d8291c0"
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
                print(f"Request failed. Retrying... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)  
                continue  
            else:
                print(e)
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
        start_line = tool_param.get('start_line', None)
        end_line = tool_param.get('end_line', None)
        observation = agent_utils.view_file_contents(file_path, index, start_line, end_line)

    elif tool_name == 'view_code_changes':
        observation = agent_utils.view_code_changes(tool_param['file_path'])
    
    elif tool_name == 'explore_project_structure':
        root_path = tool_param.get("root_path", "/")
        max_depth = tool_param.get("max_depth", 3)
        include_patterns = tool_param.get("include_patterns", None)
        exclude_patterns = tool_param.get("exclude_patterns", None)
        observation = agent_utils.explore_project_structure(root_path, max_depth, include_patterns, exclude_patterns)

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
        PR_Changed_Files=PR_Changed_Files,
        Previously_Gathered_Information=""
    ) + '\n'
    test_plan = ""
    session_message_list = []
    cache_react_pair = {}
    for i in range(1, 10):
        session_message = ''
        content = llm(config, PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, user_prompt)
        # 可能正则匹配不到
        ReAct_pair_list = extract_thought_action_pairs(content)   

        max_workers = min(len(ReAct_pair_list), 10)  # 限制10个线或对数，以较小者为准
        
        # 过程对配对使用线程池并行
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_react = {}
            
            for react in ReAct_pair_list:
                future = executor.submit(
                    process_react_pair,
                    react,
                    config,
                    agent_utils,
                    PR_Content,
                    PR_Changed_Files,
                    RELEVANCE_EVALUATION_PROMPT
                )
                future_to_react[future] = react
            
            # 过程完成后完成的任务完成
            for future in as_completed(future_to_react):
                react = future_to_react[future]
                try:
                    # 从完成的任务中获取结果
                    result = future.result()
                    # 更新反应对与结果
                    react.update(result)
                except Exception as exc:
                    print(f'Processing ReAct pair generated an exception: {exc}')
        print(f"ReAct_pair_list: \n{ReAct_pair_list}\n")
        
        ReAct_pair_list = sorted(ReAct_pair_list, key=lambda x: x['relevance'], reverse=True)
        for react_pair in ReAct_pair_list:
            react_id = react_pair['action_name'] + " " + json.dumps(react_pair['action_parameters'])

            if react_id in cache_react_pair:
                continue
            else:
                cache_react_pair[react_id] = react_pair
                win_react_pair = react_pair
                break

        # 将win_react_pair中的信息拼接到user_prompt中
        session_message += f"### Exploration Step {i}:\n"
        session_message += f"#### Thought-Action Pair {i}\n"
        session_message += f"- **Thought**: " + win_react_pair['thought'] + '\n'
        session_message += f"- **Action**: " + win_react_pair['action_name'] + '\n'
        session_message += f"- **Action Parameters**: " + json.dumps(win_react_pair['action_parameters']) + '\n'
        session_message += f"- **Action Observation**: " + win_react_pair['observation'] + '\n'
        session_message += f"- **Relevance Score**: " + str(win_react_pair['relevance']) + '\n'
        session_message += f"- **Justification**: " + win_react_pair['justification'] + '\n'
        session_message_list.append(session_message)
        
        user_prompt = PR_TEST_PLAN_EDIT_USER_PROMPT.format(
            PR_Project_Root_Dir=config['CKG']['project_dir'],
            PR_Content=PR_Content,
            PR_Changed_Files=PR_Changed_Files,
            Previously_Gathered_Information='\n\n'.join(session_message_list)
        )
        print(f"Round {i}\n")
        print(session_message)
        print("--------------------------------------\n")
    session_messages = '\n'.join(session_message_list)
    relevance_information = f"### PR Content:\n{PR_Content}\n ### PR changed files: {PR_Changed_Files}\n ### Relevant Informations: \n {session_messages}"
    # 告诉llm开始编写test plan
    test_plan_edit_promt = PR_TEST_PLAN_EDIT_PROMPT.format(
        relevance_information = relevance_information
    )
    test_plan = llm(config, system_prompt=PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, user_prompt=test_plan_edit_promt)
    # 获取当前时间并格式化为字符串
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config['Agent']['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    output_file_path = os.path.join(output_dir, f"{config['Agent']['llm_model']}_{current_time}.txt")
    # 使用当前时间作为文件名的一部分
    with open(output_file_path, 'w') as f:
        f.write(user_prompt + "\n" + test_plan)

    return test_plan
def main():
    agent('./source/config.yaml')

if __name__ == "__main__":
    main()