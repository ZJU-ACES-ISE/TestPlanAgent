import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tasks.BaseTask import BaseTask
from prompt.tot.test_plan import (
    PR_TEST_PLAN_EDIT_USER_PROMPT, 
    PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, 
    RELEVANCE_EVALUATION_PROMPT,
    PR_TEST_PLAN_EDIT_PROMPT
)

class TOT(BaseTask):
    """
    实施测试计划生成的思想树(TOT)策略。
    扩展底座类。
    """
    
    def __init__(self, config):
        """
        用提供的配置初始化TOT任务。
        
        Args:
            config (dict): 任务的配置字典
        """
        super().__init__(config)
        self.cache_react_pair = {}
    
    def extract_thought_action_pairs(self, text):
        """
        Extract LLM响应文本中的思想行动对。
        
        Args:
            text (str): LLM的响应文本
            
        Returns:
            list: 包含思想表演对的字典列表
        """
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
                    action_params_json = {"error": "Invalid JSON"}
                
                pair_dict = {
                    "id": pair_id.strip(),
                    "thought": thought_match.group(1).strip(),
                    "action_name": action_name_match.group(1).strip(),
                    "action_parameters": action_params_json,
                    "expected_information": expected_info_match.group(1).strip()
                }
                
                results.append(pair_dict)
        
        return results
    
    def extract_relevance_evaluation(self, response_text):
        """
        从LLM响应文本中提取相关性评估结果。
        
        Args:
            response_text (str): LLM的响应文本
            
        Returns:
            dict: 包含相关性得分和理由的字典
        """
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
    
    def process_react_pair(self, react):
        """
        在单独的线程中处理单个反应对。
        
        Args:
            react (dict): 包含思想表演对信息的字典
            
        Returns:
            dict: 具有观察，相关得分和理由的字典
        """
        thought = react['thought']
        action_name = react['action_name']
        action_param = react['action_parameters']
        
        # 执行工具
        try:
            observation = self.execute_tool(action_name, action_param)
        except Exception as e:
            observation = str(e)
        
        # 创建相关性评估提示
        evaluate_ReAct_relevance_prompt = RELEVANCE_EVALUATION_PROMPT.format(
            PR_Content=self.PR_Content,
            PR_Changed_Files=self.PR_Changed_Files,
            Thought=thought,
            Action_Name=action_name,
            Action_Parameters=json.dumps(action_param),
            Action_Observation=observation
        )
        
        # 评估相关性
        content = self.llm(PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, evaluate_ReAct_relevance_prompt, self.config['Agent']['llm_model'])
        relevance = self.extract_relevance_evaluation(content)
        
        # 返回结果
        return {
            'observation': observation,
            'relevance': relevance['score'],
            'justification': relevance['justification']
        }
    
    def run(self):
        """
        运行TOT任务以生成测试计划。
        
        Returns:
            str: 生成的测试计划
        """
        user_prompt = PR_TEST_PLAN_EDIT_USER_PROMPT.format(
            PR_Project_Root_Dir=self.config['CKG']['project_dir'],
            PR_Content=self.PR_Content,
            PR_Changed_Files=self.PR_Changed_Files,
            Previously_Gathered_Information=""
        ) + '\n'
        
        test_plan = ""
        session_message_list = []
        
        # 运行10次迭代
        for i in range(1, 10):
            # 从LLM获取内容
            content = self.llm(PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, user_prompt, self.config['Agent']['llm_model'])
            
            # 提取思想行动对
            ReAct_pair_list = self.extract_thought_action_pairs(content)
            
            # 设置最大工人进行并行处理
            max_workers = min(len(ReAct_pair_list), 10)
            
            # 并行过程对
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_react = {}
                
                for react in ReAct_pair_list:
                    future = executor.submit(self.process_react_pair, react)
                    future_to_react[future] = react
                
                # 流程完成的任务
                for future in as_completed(future_to_react):
                    react = future_to_react[future]
                    try:
                        # 从完成任务中获得结果
                        result = future.result()
                        # 更新反应对与结果配对
                        react.update(result)
                    except Exception as exc:
                        print(f'Processing ReAct pair generated an exception: {exc}')
            
            print(f"ReAct_pair_list: \n{ReAct_pair_list}\n")
            
            # 按相关得分对成对（下降）
            ReAct_pair_list = sorted(ReAct_pair_list, key=lambda x: x['relevance'], reverse=True)
            
            # 选择以前尚未使用的得分最高的对
            win_react_pair = None
            for react_pair in ReAct_pair_list:
                react_id = react_pair['action_name'] + " " + json.dumps(react_pair['action_parameters'])
                
                if react_id not in self.cache_react_pair:
                    self.cache_react_pair[react_id] = react_pair
                    win_react_pair = react_pair
                    break
            
            if win_react_pair is None:
                print("No new ReAct pairs found.")
                break
            
            # 格式化会话消息
            session_message = f"### Exploration Step {i}:\n"
            session_message += f"#### Thought-Action Pair {i}\n"
            session_message += f"- **Thought**: " + win_react_pair['thought'] + '\n'
            session_message += f"- **Action**: " + win_react_pair['action_name'] + '\n'
            session_message += f"- **Action Parameters**: " + json.dumps(win_react_pair['action_parameters']) + '\n'
            session_message += f"- **Action Observation**: " + str(win_react_pair['observation']) + '\n'
            session_message += f"- **Relevance Score**: " + str(win_react_pair['relevance']) + '\n'
            session_message += f"- **Justification**: " + win_react_pair['justification'] + '\n'
            
            session_message_list.append(session_message)
            
            # 更新用户提示进行下一个迭代
            user_prompt = PR_TEST_PLAN_EDIT_USER_PROMPT.format(
                PR_Project_Root_Dir=self.config['CKG']['project_dir'],
                PR_Content=self.PR_Content,
                PR_Changed_Files=self.PR_Changed_Files,
                Previously_Gathered_Information='\n\n'.join(session_message_list)
            )
            
            print(f"Round {i}\n")
            print(session_message)
            print("--------------------------------------\n")
        
        # 结合所有会话消息
        session_messages = '\n'.join(session_message_list)
        
        # 为生成测试计划创建相关信息
        relevance_information = (
            f"### PR Content:\n{self.PR_Content}\n"
            f"### PR changed files: {self.PR_Changed_Files}\n"
            f"### Relevant Informations: \n {session_messages}"
        )
        
        # 生成测试计划
        test_plan_edit_prompt = PR_TEST_PLAN_EDIT_PROMPT.format(
            relevance_information=relevance_information
        )
        
        test_plan = self.llm(
            system_prompt=PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, 
            user_prompt=test_plan_edit_prompt
        )
        
        # 保存结果
        self.save_result(user_prompt + "\n" + test_plan, test_plan)
        
        return test_plan