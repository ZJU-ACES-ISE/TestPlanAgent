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
        self.PR_Changed_Files = self.agent_utils.get_code_changes_summary()
        
    @staticmethod
    def llm(system_prompt, user_prompt, model):
        """
        用给定的提示调用语言模型API。
        
        Args:
            system_prompt (str): 系统提示为LLM
            user_prompt (str, optional): 用户提示llm
            
        Returns:
            str: LLM响应内容
        """
        def get_model_limits(model):
            """
            获取特定模型的最大上下文长度和最大输出长度。
            
            Args:
                model (str): 模型名称
                
            Returns:
                tuple: (最大上下文长度, 最大输出长度)
            """
            # 定义各模型的默认限制
            model_limits = {
                'claude-3-7-sonnet-20250219': {
                    'context_length': 100000,
                    'max_output_length': 4096
                },
                'deepseek-chat': {
                    'context_length': 63000,
                    'max_output_length': 8000  # 默认最大输出长度为4K
                },
                'qwen-max-latest': {
                    'context_length': 108000,
                    'max_output_length': 8000
                },
                'gpt-3.5-turbo': {
                    'context_length': 14385,
                    'max_output_length': 4096
                },
                'qwen-coder-32B': {
                    'context_length': 46000,
                    'max_output_length': 8000
                },
                'qwen2.5-coder-32b-instruct': {
                    'context_length': 128000,
                    'max_output_length': 8000
                },
                'qwen2.5-coder-14b-instruct': {
                    'context_length': 128000,
                    'max_output_length': 8000
                },
                'qwen-coder-14B': {
                    'context_length': 46000,
                    'max_output_length': 8000
                },
                'gpt-4o':{
                    'context_length': 128000,
                    'max_output_length': 16384
                }
            }
            
            # 尝试获取确切模型的限制，如果不存在，则基于模型名称的部分匹配
            if model in model_limits:
                return model_limits[model]['context_length'], model_limits[model]['max_output_length']
            
            # 部分匹配
            for model_name, limits in model_limits.items():
                if model_name in model:
                    return limits['context_length'], limits['max_output_length']
            
            # 如果没有匹配项，返回默认值
            # print(f"警告: 未知模型 '{model}'，使用默认上下文限制。")
            return 46000, 8000  # 保守的默认值

        def estimate_token_count(text, model):
            """
            估计文本中的token数量。
            
            Args:
                text (str): 要估计的文本
                
            Returns:
                int: 估计的token数量
            """
            # 一个非常粗略的估计：约4个字符等于1个token
            # 对于中文，大约每个汉字是一个token
            if 'deepseek' in model:
                return Agent_utils.cal_deepseek_token(text)
            elif 'gpt' in model:
                return Agent_utils.cal_gpt_token(text)
            elif 'qwen' in model:
                return Agent_utils.cal_qwen_token(text)
            chinese_char_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
            other_char_count = len(text) - chinese_char_count
            
            return chinese_char_count + other_char_count // 4

        def truncate_prompts(system_prompt, user_prompt, model, context_length, max_output_length):
            """
            根据模型的最大上下文长度，在必要时截断系统提示和用户提示。
            
            Args:
                system_prompt (str): 系统提示
                user_prompt (str): 用户提示
                model (str): 模型名称
                context_length (int): 模型的最大上下文长度
                max_output_length (int): 模型的最大输出长度
                
            Returns:
                tuple: (截断后的系统提示, 截断后的用户提示)
            """
            # 估计当前提示的token数量
            system_tokens = estimate_token_count(system_prompt, model)
            user_tokens = estimate_token_count(user_prompt, model)
            
            # 为输出保留空间
            available_tokens = context_length - max_output_length
            current_total = system_tokens + user_tokens
            
            truncated_flag = False
            # 如果总token数超过了可用的token数，需要截断
            if current_total > available_tokens:
                truncated_flag = True
                # 计算需要减少的token数量
                excess_tokens = current_total - available_tokens
                
                # 优先截断用户提示，保留系统提示
                if excess_tokens < user_tokens:
                    # 只需要截断用户提示
                    token_ratio = (user_tokens - excess_tokens) / user_tokens
                    # 根据token比例截断文本
                    chars_to_keep = int(len(user_prompt) * token_ratio)
                    user_prompt = user_prompt[:chars_to_keep]
                    print(f"警告: 用户提示已截断，从 {user_tokens} tokens 减少到约 {user_tokens - excess_tokens} tokens。")
                else:
                    # 需要同时截断系统提示和用户提示
                    # 首先将用户提示减少到其大小的25%
                    user_token_reduction = min(excess_tokens, int(user_tokens * 0.75))
                    token_ratio = (user_tokens - user_token_reduction) / user_tokens
                    chars_to_keep = int(len(user_prompt) * token_ratio)
                    user_prompt = user_prompt[:chars_to_keep]
                    
                    # 如果仍然需要减少更多token
                    remaining_excess = excess_tokens - user_token_reduction
                    if remaining_excess > 0:
                        # 也截断系统提示
                        token_ratio = (system_tokens - remaining_excess) / system_tokens
                        chars_to_keep = max(int(len(system_prompt) * token_ratio), 100)  # 保留至少100个字符
                        system_prompt = system_prompt[:chars_to_keep]
                        print(f"警告: 系统提示已截断，从 {system_tokens} tokens 减少到约 {system_tokens - remaining_excess} tokens。")
                    
                    print(f"警告: 用户提示已大幅截断，从 {user_tokens} tokens 减少到约 {user_tokens - user_token_reduction} tokens。")
            
            return system_prompt, user_prompt, truncated_flag
 
        # 获取模型的最大上下文长度和最大输出长度
        context_length, max_output_length = get_model_limits(model)
        
        # 估计token数量并在必要时截断提示
        system_prompt, user_prompt, truncated = truncate_prompts(system_prompt, user_prompt, model, context_length, max_output_length)

        # if 'deepseek' in model:
            # -官网
            # api_key = "sk-da7a5e373876461f9efb80e7c15828a5"
            # url = "https://api.deepseek.com/chat/completions"
            # -阿里
            # api_key = "sk-6072ffbc181542f2862a1fd04d8291c0"
            # url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            # -openrouter
            # api_key = "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"
            # url  = "https://openrouter.ai/api/v1/chat/completions"
            # model = "deepseek/deepseek-chat-v3-0324:free"
            # -火山
            # api_key = "ca571e3f-f63c-415f-a6ff-571519d9a72c"
            # url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        if 'qwen' in model:
            api_key = "sk-6072ffbc181542f2862a1fd04d8291c0"
            # url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            # api_key = "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"
            # url  = "https://openrouter.ai/api/v1/chat/completions"
            url = "http://localhost:8000/v1/chat/completions"
        else:
            api_key = "sk-wvvB8thiOVcpwJw1i4OI4FqFSItWyC5IePz3hAgrOJ0Jh1MY"
            # if 'claude' in model:
            #     url = "https://api.chatanywhere.tech/v1/messages"
            # else:
            url = "https://api.chatanywhere.tech/v1/chat/completions"

        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # if 'claude' in model:
        #     data = {
        #         "model": model,
        #         "system": system_prompt,
        #         "messages": [
        #             {"role": "user", "content": user_prompt}
        #         ],
        #         "temperature": 0.2
        #     }
        # else:    
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
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
                    time.sleep(1 ** attempt)
                    continue
                else:
                    print(e)
                    raise e
        
        response_dict = json.loads(response.text.strip())
        # if 'claude' in model:
        #     content = response_dict["content"][0]["text"]
        # else:    
        content = response_dict['choices'][0]['message']['content']
        return content, truncated
    
    
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
            cursor = tool_param.get('cursor', 0)
            page_size = tool_param.get('page_size', 100)
            observation = self.agent_utils.search_files_path_by_pattern(pattern, cursor, page_size)
        
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
        elif tool_name == 'list_directory_contents':
            directory_path = tool_param.get("directory_path", "/")
            observation = self.agent_utils.list_directory_contents(directory_path)
        else:
            observation = json.dumps({"error": f"{tool_name} is an incorrect tool name, please do not use tools other than those provided, please correct."})
        return observation
    
    def save_result(self, trajectory):
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
            json.dump(trajectory, f)
        
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