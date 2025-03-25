import os
import requests
import json
import time
from tqdm import tqdm  # 用于进度条

with open('data/PR_URL_for_test.json', 'r') as f:
    data = json.load(f)

def get_body_from_pr(url, max_retries=3):
    # token = os.environ.get('GITHUB_ACCESS_TOKEN')
    token = "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"

    headers = {
        'Authorization': f'token {token}', 
        'Accept': 'application/vnd.github.v3+json', 
    }
    
    # 添加重传机制
    for retry in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)  # 添加超时设置
            
            # 检查是否达到API限制
            if response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                # 如果达到限制，等待一段时间后重试
                wait_time = 60 * (retry + 1)  # 指数退避：每次等待时间递增
                print(f"API rate limit exceeded. Waiting for {wait_time} seconds before retry...")
                time.sleep(wait_time)
                continue
                
            # 如果请求成功，处理响应
            if response.status_code == 200:
                comments = response.json()
                valid_comments = []
                for comment in comments:
                    if comment['user']['type'] != 'Bot':
                        valid_comments.append(comment['body'])
                return valid_comments
            
            # 如果是其他错误，打印信息并重试
            print(f"Request failed with status code {response.status_code}. Retrying ({retry+1}/{max_retries})...")
            time.sleep(2 * (retry + 1))  # 指数退避
            
        except requests.exceptions.RequestException as e:
            # 处理请求异常（超时、连接错误等）
            print(f"Request error: {e}. Retrying ({retry+1}/{max_retries})...")
            time.sleep(2 * (retry + 1))  # 指数退避
    
    # 如果所有重试都失败，返回空列表
    print(f"All retries failed for URL: {url}")
    return []

total_comments = {}
# 项目进度条
for project in tqdm(data, desc="Processing projects"):
    project_total_comments = {}
    if project == 'Expensify':
        continue
    # 每个项目的PR进度条
    for pr_url in tqdm(data[project], desc=f"Processing {project} PRs", leave=False):
        sub_pr_url = pr_url.split("https://")
        pr_url = sub_pr_url[1]
        pr_url_parts = pr_url.split("/")
        repo = pr_url_parts[1]
        user = pr_url_parts[2]
        pull_number = pr_url_parts[4]

        issue_comments_api_url = f"https://api.github.com/repos/{repo}/{user}/issues/{pull_number}/comments"
        review_comments_api_url = f"https://api.github.com/repos/{repo}/{user}/pulls/{pull_number}/comments"

        issue_comments = get_body_from_pr(issue_comments_api_url)
        review_comments = get_body_from_pr(review_comments_api_url)

        comments = issue_comments + review_comments
        
        project_total_comments[pull_number] = comments
    total_comments[project] = project_total_comments

with open('data/pr_full_comments.json', 'w') as f:
    json.dump(total_comments, f)