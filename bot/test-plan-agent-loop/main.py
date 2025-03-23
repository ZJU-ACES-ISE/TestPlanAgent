import requests
import time
import json
import re
import os
import sys
from pathlib import Path
from make_run_config_file import generate_config, save_config
from agent.test_plan_agent_v1_1 import agent
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

# GitHub API配置
GITHUB_TOKEN = "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"
POLLING_INTERVAL = 7  # 秒
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

output_file_name  = ""
model = "gpt-4o"
api = "https://api.gptsapi.net/v1/chat/completions"
output = "./source/config.yaml"
output_dir = None


# 存储已处理的通知ID
PROCESSED_NOTIFICATIONS_FILE = "processed_notifications.json"

def load_processed_notifications():
    if os.path.exists(PROCESSED_NOTIFICATIONS_FILE):
        with open(PROCESSED_NOTIFICATIONS_FILE, "r") as f:
            return json.load(f)
    return []

def save_processed_notification(comment_id):
    processed = load_processed_notifications()
    if comment_id not in processed:
        processed.append(comment_id)
        with open(PROCESSED_NOTIFICATIONS_FILE, "w") as f:
            json.dump(processed, f)

def get_mentions():
    response = requests.get(
        "https://api.github.com/notifications",
        headers=HEADERS
    )
    
    if response.status_code != 200:
        print(f"Error fetching notifications: {response.status_code}")
        return []
    
    notifications = response.json()
    # 过滤出reason为mention的通知
    mention_notifications = [n for n in notifications if n.get("reason") == "mention"]
    return mention_notifications

def get_notification_content(notification):
    # 获取通知的具体内容
    subject_url = notification.get("subject", {}).get("latest_comment_url")
    if not subject_url:
        return None
    
    response = requests.get(subject_url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error fetching notification content: {response.status_code}")
        return None
    
    return response.json()

def is_test_plan_command(content_body):
    # 检查内容中是否有/test-plan命令
    return "/test-plan" in content_body

def get_pr_url_from_notification(notification):
    # 从通知中提取PR URL
    html_url = notification.get("subject", {}).get("url", "")
    # 将API URL转换为网页URL
    if "api.github.com/repos" in html_url:
        html_url = html_url.replace("api.github.com/repos", "github.com")
        if "/pulls/" in html_url:
            html_url = html_url.replace("/pulls/", "/pull/")
    return html_url

def create_test_plan(pr_url):
    # 调用测试计划API
    config = generate_config(pr_url, output_file_name, model, output_dir)
    save_config(config, output_dir)
    test_plan = agent()
    
    if test_plan != "":
        return test_plan
    return None

def post_comment_to_pr(pr_url, comment):
    # 从PR URL中提取owner, repo和PR number
    # 示例PR URL: https://github.com/owner/repo/pull/123
    match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        print(f"Invalid PR URL: {pr_url}")
        return False
    
    owner, repo, pr_number = match.groups()
    
    # 构建评论API URL
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    
    # 发送评论
    response = requests.post(
        comments_url,
        headers=HEADERS,
        json={"body": comment}
    )
    
    return response.status_code == 201
def main():
    
    print("Starting GitHub mention monitor...")
    
    while True:
        try:
            processed_comments = load_processed_notifications()
            mentions = get_mentions()
            
            for notification in mentions:
                notification_id = notification.get("id")
                comment_id = notification.get("subject").get("latest_comment_url").split(os.path.sep)[-1]
                # 跳过已处理的通知
                if comment_id in processed_comments:
                    continue
                
                # 获取通知内容
                content = get_notification_content(notification)
                if not content:
                    continue
                
                body = content.get("body", "")
                
                # 检查是否包含测试计划命令
                if is_test_plan_command(body):
                    print(f"Test plan command detected in notification {comment_id}")
                    
                    # 获取PR URL
                    pr_url = get_pr_url_from_notification(notification)
                    if not pr_url:
                        continue
                    
                    # 生成测试计划
                    pr_api_url = notification.get("subject", {}).get("url", "")

                    test_plan = create_test_plan(pr_api_url)
                    # test_plan = "a test plan"
                    if not test_plan:
                        continue
                    
                    # 发表评论
                    comment = f"# Test Plan\n\n{test_plan}\n\n*自动生成的测试计划*"
                    success = post_comment_to_pr(pr_url, comment)
                    
                    if success:
                        print(f"Successfully posted test plan comment to {pr_url}")
                    else:
                        print(f"Failed to post comment to {pr_url}")
                
                # 标记通知为已处理
                save_processed_notification(comment_id)
                
                # 可选：将通知标记为已读
                mark_notification_as_read(notification_id)
            
            # 等待下一次轮询
            time.sleep(POLLING_INTERVAL)
            
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            time.sleep(POLLING_INTERVAL)

def mark_notification_as_read(notification_id):
    response = requests.patch(
        f"https://api.github.com/notifications/threads/{notification_id}",
        headers=HEADERS
    )
    return response.status_code == 205

if __name__ == "__main__":
    main()