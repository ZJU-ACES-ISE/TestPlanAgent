import os
import json
from datetime import datetime
from tasks.BaseTask import BaseTask
from prompt.test_plan_agent_prompt_v4_6 import PR_TEST_PLAN_EDIT_USER_PROMPT, PR_TEST_PLAN_EDIT_SYSTEM_PROMPT

class ReAct(BaseTask):
    """
    实施测试计划生成的React策略。
    扩展底座类。
    """
    
    def __init__(self, config):
        """
        用提供的配置初始化React任务。
        
        Args:
            config (dict): Configuration dictionary for the task
        """
        super().__init__(config)
    
    def run(self):
        """
        运行React任务以生成测试计划。
        
        Returns:
            str: 生成的测试计划
        """
        print("starting generating test plan......")
        user_prompt = PR_TEST_PLAN_EDIT_USER_PROMPT.format(
            PR_Project_Root_Dir=self.config['CKG']['project_dir'],
            PR_Content=self.PR_Content,
            PR_Changed_Files=self.PR_Changed_Files
        ) + '\n'
        
        test_plan = ""
        session_messages = []
        
        # 最多可以进行20次迭代
        for i in range(1, 20):
            content = self.llm(PR_TEST_PLAN_EDIT_SYSTEM_PROMPT, user_prompt, self.config['Agent']['llm_model'])
            
            # 检查测试计划是否完成
            if 'Test Plan Details' in content:
                thought_content = ''.join(content.split('Thought')[1].split('Test Plan Details')[0].split(':')[1:]).replace('#', '').strip()
                
                session_message = f"Thought {i}: " + thought_content + '\n'
                test_plan = '\n'.join(content.split('Test Plan Details')[1].splitlines()[1:]).replace('```', '').strip()
                session_message += f"Test Plan: \n" + test_plan + '\n'
                
                user_prompt += session_message
                session_messages.append(session_message)
                break
            else:
                # 提取思想和行动
                thought_content = ''.join(content.split('Thought')[1].split('Action')[0].split(':')[1:]).replace('#', '').strip()
                action_name = content.split('Action')[1].splitlines()[1].replace('```','').strip()
                
                try:
                    action_param = json.loads(''.join(content.split('Action')[1].splitlines()[2:]).replace('```', ''))
                except json.JSONDecodeError:
                    action_param = {}
                
                # 验证是否存在所需的组件
                if action_name == '' or thought_content == '' or action_param is None:
                    print("Some components are empty, please check")
                    print(content + '\n')
                    print(f"Thought {i}: " + thought_content + '\n' + f"Action {i}: " + action_name + '\n' + json.dumps(action_param) +'\n')
                    break
                
                # 执行工具并观察
                try:
                    observation = self.execute_tool(action_name, action_param)
                except:
                    print(f"Error occurred during execution. action_param is {action_param}")
                    observation = ""
                observation_str = json.dumps(observation) if isinstance(observation, (dict, list)) else observation
                
                # 格式化会话消息
                session_message = (
                    f"Thought {i}: " + thought_content + '\n' + 
                    f"Action {i}: " + action_name + '\n' + 
                    json.dumps(action_param) + '\n' + 
                    f"Observation {i}: " + observation_str + '\n'
                )
                
                user_prompt += session_message
                session_messages.append(session_message)
                
                print(f"Round {i}\n")
                print(session_message)
                print("--------------------------------------\n")
        
        # 保存结果
        self.save_result(user_prompt)
        
        return test_plan