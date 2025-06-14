import json
from bert_score import score

import os 
# 计算BLEU/ROUGE
result_dir = "./result/backup-with-git-diff-full/ReAct"
compare_pair = {}
# 获取ref test plan以及 candidate test plan
for repo in os.listdir(result_dir):
    repo_dir = os.path.join(result_dir, repo)
    if os.path.isdir(repo_dir):
        PR_content_dir = os.path.join(repo_dir, "PR-Content")
        if os.path.isdir(PR_content_dir):
            PR_content_list = os.listdir(PR_content_dir)
            for PR_content in PR_content_list:
                pull_number = PR_content.split("_")[0]
                PR_content_file_dir = os.path.join(PR_content_dir, PR_content)
                if os.path.isfile(PR_content_file_dir):
                    with open(PR_content_file_dir, 'r') as f:
                        PR_content_json = json.load(f)
                    compare_pair[pull_number] = []
                    compare_pair[pull_number].append(PR_content_json["Test_Plan"])
        Test_plan_dir = os.path.join(repo_dir, "Test-Plan")
        if os.path.isdir(Test_plan_dir):
            Test_plan_list = os.listdir(Test_plan_dir)
            for Test_plan in Test_plan_list:
                if "gpt-4o" in Test_plan:
                    PR_content_file_dir = os.path.join(Test_plan_dir, Test_plan)
                    pull_number = PR_content_file_dir.split("_")[-1].split(".")[0]
                    if os.path.isfile(PR_content_file_dir):
                        with open(PR_content_file_dir, 'r') as f:
                            PR_content_json = json.load(f)
                        compare_pair[pull_number].append(PR_content_json["react_info"][-1]["test_plan"])
# print(compare_pair['16418'][0])
for value in compare_pair.values():
    if len(value) != 2:
        print(value)
        print("error")
        break

references = [value[0] for value in compare_pair.values()]
predictions =[value[1] for value in compare_pair.values()]

P, R, F1 = score(predictions, references, lang="en", verbose=True)