import json
import os
from pathlib import Path
import sys
import time
import requests
import yaml
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

from prompt.test_plan_llm_judge_prompt_v1_1 import PR_TEST_PLAN_SCORING_SYSTEM_PROMPT, PR_TEST_PLAN_SCORING_USER_PROMPT
from utils.tools import reformat_pr_info_for_user_prompt

with open('./source/config.yaml', 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

test_plan_result_path = os.path.join(config['Agent']['output_dir'], config['Agent']['output_file_name'])

with open(test_plan_result_path, 'r') as f:
    test_plan_result = f.readlines()


reformat_pr_info = reformat_pr_info_for_user_prompt()
PR_Content = reformat_pr_info['PR_Content']
PR_Test_Plan = reformat_pr_info['Test_Plan']
PR_Changed_Files = reformat_pr_info['PR_Changed_Files']

def llm(system_prompt, user_prompt):

    api_key = os.environ.get("OPENAI_API_KEY")

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

def judger():
    Reference_Steps = PR_Test_Plan
    Candidate_Steps = ''.join(test_plan_result).split("## 4. Test Cases")[1].strip()
    user_prompt = PR_TEST_PLAN_SCORING_USER_PROMPT.format(
        PR_Content=PR_Content,
        Reference_Steps=Reference_Steps,
        Candidate_Steps=Candidate_Steps
    ) + '\n'
    llm_repsonse = llm(PR_TEST_PLAN_SCORING_SYSTEM_PROMPT, user_prompt)
    scores = json.loads(llm_repsonse.replace("```","").replace('json',''))
    scores_dir = os.path.join(config['Agent']['output_dir'], "scores")
    os.makedirs(scores_dir, exist_ok=True)
    file_number = len(os.listdir(scores_dir)) + 1
    scores_path = os.path.join(scores_dir, f"scores_{file_number}.json")
    with open(scores_path, 'w') as f:
        json.dump(scores, f)
def main():
    judger()

if __name__ == "__main__":
    main()