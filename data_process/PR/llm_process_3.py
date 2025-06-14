import os
import requests
import json

import yaml



with open('./source/config.yaml', 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

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

def pr_commits():
    owner = "veteran-2022"  # Replace with the repository owner (e.g., GitHub username or org)
    repo = "rec_movies-master"  # Replace with the repository name
    pr_number = 2  # Replace with the pull request number you want to fetch
    token = "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"  # Replace with your GitHub personal access token
    
    # pr_restructure(owner, repo, pr_number, token)
    pr_commits = get_pull_request_commits(owner, repo, pr_number, token)
    with open('./log/pr_commits.json', 'w') as json_file:
        json.dump(pr_commits, json_file, indent=4)

def llm_restructure_pr_body(config, pr_body):
    from tasks.BaseTask import BaseTask

    # api_key = os.environ.get("OPENAI_API_KEY")
    # api_key = config['Agent']['api_key']
    # url = config['Agent']['llm_url'] 

    # Prompt to guide the LLM in restructuring the PR body
    user_prompt = f"""
        Please carefully analyze the following pull request description to extract and separate the test plan from other content.

        ### INSTRUCTIONS:

        1. IDENTIFY the test plan section by looking for:
        - Explicit "Test Plan" headings (case-insensitive, may include "Testing Plan", "How to Test", "Testing",etc.)
        - Sections describing testing procedures, verification steps, or validation methods
        - Instructions for reviewers on how to verify the changes

        2. PRESERVE EXACTLY:
        - All original formatting including code blocks, bullet points, and indentation
        - All code snippets within the test plan (do not summarize or alter code)
        - All links, references, and technical details

        3. DO NOT:
        - Add your own commentary or analysis about the test plan
        - Modify or "improve" the test plan content
        - Include non-test plan content in the test plan section

        4. SEPARATE content into two distinct sections:
        - "Description of changes": Everything that is NOT part of the test plan
        - "Test plan": ONLY the content specifically related to testing or verification

        5. FORMAT the output JSON correctly
        

        If no test plan is found, use "None" for the test plan value.

        ### PR Description:
        {pr_body}

        Return ONLY the following JSON format (preserve all formatting within the values):
        {{
            "Description of changes": "<change_description_with_original_formatting>",
            "Test plan": "<test_plan_with_original_formatting_or_None>"
        }}
    """

    result, _ = BaseTask.llm("", user_prompt, config['Agent']['llm_model'])
    return result

def pr_restructure(owner, repo, pr_number, token):
    pr_details = get_pull_request(owner, repo, pr_number, token)

    restructured_pr_body = llm_restructure_pr_body(pr_details['body'])
    
    restructured_pr_body = restructured_pr_body.strip('```json').strip('```')
    print(restructured_pr_body)
    json_content = json.loads(restructured_pr_body)

    #将 JSON 对象保存到文件中
    with open('./log/SONAR_restructed_pr_output.json', 'w') as json_file:
        json.dump(json_content, json_file, indent=4)

if __name__ == "__main__":
    # pr_commits()
    pr_restructure("veteran-2022", "rec_movies-master", 2, "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")
    # pr_restructure("facebookresearch", "SONAR", 37, "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")