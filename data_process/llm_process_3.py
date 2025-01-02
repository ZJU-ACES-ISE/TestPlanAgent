import os
import requests
import json

def get_pull_request(owner, repo, pr_number, token):
    
    # GitHub API URL to get a pull request
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    
    # Headers to authenticate the request
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }
    
    # Send GET request to GitHub API
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        # Successfully fetched the PR details
        return response.json()
    else:
        # Handle errors (e.g., PR not found, invalid token, etc.)
        return {"error": f"Failed to get PR {pr_number}. Status code: {response.status_code}", "details": response.json()}

def get_pull_request_commits(owner, repo, pr_number, token):
     # GitHub API URL to get a pull request
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    
    # Headers to authenticate the request
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }
    
    # Send GET request to GitHub API
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        # Successfully fetched the PR details
        return response.json()
    else:
        # Handle errors (e.g., PR not found, invalid token, etc.)
        return {"error": f"Failed to get PR {pr_number} commits. Status code: {response.status_code}", "details": response.json()}

def restructure_pr_body(pr_body):

    api_key = os.environ.get("OPENAI_API_KEY")
    url = "https://api.gptsapi.net/v1/chat/completions"  # 自定义的base URL

    # Prompt to guide the LLM in restructuring the PR body
    prompt = f"""
    Please analyze the following pull request description to determine whether there is a test plan, and then reconstruct it into three parts:
    1. "Description of changes": A brief description of the changes made.
    2. "Test plan": A detailed plan for how the changes should be executed or tested.
    3. "Others": Any additional relevant information or context.
    If there is no test plan, please follow the following steps:
    1. "Description of changes": A brief description of the changes made.
    2. "Test plan": "None"
    3. "Others": Any additional relevant information or context.

    PR Description:
    {pr_body}

    Provide the result in the following format:
    {{
        "Description of changes": "<change_description>",
        "Test plan": "<execution_plan>",
        "Others": "<other>"
    }}
    """

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
    
    response_dict = json.loads(response.text.strip())
    # Parse the result
    return response_dict['choices'][0]['message']['content']


def pr_restructure(owner, repo, pr_number, token):
    pr_details = get_pull_request(owner, repo, pr_number, token)

    restructured_pr_body = restructure_pr_body(pr_details['body'])
    
    restructured_pr_body = restructured_pr_body.strip('```json').strip('```')
    print(restructured_pr_body)
    json_content = json.loads(restructured_pr_body)

    #将 JSON 对象保存到文件中
    with open('output.json', 'w') as json_file:
        json.dump(json_content, json_file, indent=4)
# Example usage
if __name__ == "__main__":
    owner = "veteran-2022"  # Replace with the repository owner (e.g., GitHub username or org)
    repo = "rec_movies-master"  # Replace with the repository name
    pr_number = 2  # Replace with the pull request number you want to fetch
    token = "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"  # Replace with your GitHub personal access token
    
    # pr_restructure(owner, repo, pr_number, token)
    pr_commits = get_pull_request_commits(owner, repo, pr_number, token)
    with open('./log/pr_commits.json', 'w') as json_file:
        json.dump(pr_commits, json_file, indent=4)
    # print(pr_details)
    
