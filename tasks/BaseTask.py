import os
import json
import yaml
import requests
import time
from abc import ABC, abstractmethod
from datetime import datetime
from utils.tools import Agent_utils

class BaseTask(ABC):
    """
    所有测试计划生成任务的基础抽象类。
    该类定义了共同的接口并提供共享功能。
    """
    
    def __init__(self, config):
        """
        用提供的配置初始化任务。
        
        Args:
            config (dict): 任务的配置字典
        """
        self.config = config
        self.agent_utils = Agent_utils(config)
        self.reformat_pr_info = self.agent_utils.reformat_pr_info_for_user_prompt()
        self.PR_Content = self.reformat_pr_info['PR_Content']
        self.PR_Changed_Files = self.reformat_pr_info['PR_Changed_Files']
    
    def llm(self, system_prompt, user_prompt, model):
        """
        用给定的提示调用语言模型API。
        
        Args:
            system_prompt (str): 系统提示为LLM
            user_prompt (str, optional): 用户提示llm
            
        Returns:
            str: LLM响应内容
        """
            # Default API settings based on model
        
        if 'deepseek' in model or 'qwen' in model:
            api_key = "sk-6072ffbc181542f2862a1fd04d8291c0"
            url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        else:
            api_key = os.environ.get('OPENAI_API_KEY')
            if 'claude' in model:
                url = "https://api.gptsapi.net/v1/messages"
            else:
                url = "https://api.gptsapi.net/v1/chat/completions"

        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        if 'claude' in model:
            data = {
                "model": model,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ]
            }
        else:    
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
        
        max_retries = 5
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
        if 'claude' in model:
            content = response_dict["content"][0]["text"]
        else:    
            content = response_dict['choices'][0]['message']['content']
        return content
    
    def execute_tool(self, tool_name, tool_param):
        """
        根据工具名称和参数执行工具。
        
        Args:
            tool_name (str): 执行工具的名称
            tool_param (dict): 工具的参数
            
        Returns:
            dict or str: 执行工具的结果
        """
        observation = ''
        
        if tool_name == 'search_class_in_project' or tool_name == 'search_function_in_project':
            entity_type = tool_name.split('_')[1]
            tool_params_name = tool_param.get(f"{entity_type}_name", '')
            observation = self.agent_utils.search_entity_in_project(tool_params_name)
        
        elif tool_name == 'search_code_dependencies':
            entity_name = tool_param.get('entity_name', '')
            observation = self.agent_utils.search_code_dependencies(entity_name)
        
        elif tool_name == 'search_files_path_by_pattern':
            pattern = tool_param.get('pattern', '')
            observation = self.agent_utils.search_files_path_by_pattern(pattern)
        
        elif tool_name == 'view_file_contents':
            file_path = tool_param.get('file_path', '')
            index = tool_param.get('index', 0)
            start_line = tool_param.get('start_line', None)
            end_line = tool_param.get('end_line', None)
            observation = self.agent_utils.view_file_contents(file_path, index, start_line, end_line)
        
        elif tool_name == 'view_code_changes':
            file_path = tool_param.get('file_path', '')
            observation = self.agent_utils.view_code_changes(file_path)
        
        elif tool_name == 'explore_project_structure':
            root_path = tool_param.get("root_path", "/")
            max_depth = tool_param.get("max_depth", 3)
            include_patterns = tool_param.get("include_patterns", None)
            exclude_patterns = tool_param.get("exclude_patterns", None)
            observation = self.agent_utils.explore_project_structure(root_path, max_depth, include_patterns, exclude_patterns)
        
        return observation
    
    def save_result(self, user_prompt, test_plan=""):
        """
        保存任务的结果。
        
        Args:
            user_prompt (str): 任务中使用的用户提示
            test_plan (str, optional): 生成的测试计划
            
        Returns:
            str: 保存输出文件的路径
        """
        # current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = self.config['Agent']['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        output_file_path = os.path.join(output_dir, self.config['Agent']['output_file_name'])
        
        with open(output_file_path, 'w') as f:
            f.write(user_prompt + "\n" + test_plan)
        
        return output_file_path
    
    @abstractmethod
    def run(self):
        """
        运行任务以生成测试计划。
        此方法必须由所有子类实现。
        
        Returns:
            str: 生成的测试计划
        """
        pass