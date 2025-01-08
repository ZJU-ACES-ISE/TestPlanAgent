import os
from zoneinfo import ZoneInfo
import requests
import datetime
from dateutil import parser
from dotenv import load_dotenv
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 加载 .env 文件
load_dotenv()

# 从环境变量中读取 GitHub Token
token = os.getenv('GITHUB_ACCESS_TOKEN')

if not token:
    raise ValueError("请在环境变量中设置 GITHUB_TOKEN")

# GitHub GraphQL API 的 URL
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# GraphQL 查询，添加 rateLimit 信息
QUERY = """
query ($searchQuery: String!, $first: Int!, $after: String) {
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
  search(query: $searchQuery, type: ISSUE, first: $first, after: $after) {
    issueCount
    edges {
      node {
        ... on PullRequest {
          title
          url
          createdAt
          mergedAt
          number
          author {
            login
          }
          baseRefName
          headRefName
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# 定义请求头部
HEADERS = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 配置重试策略
def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,  # 总重试次数
        backoff_factor=1,  # 退避因子：第一次重试等待1秒，第二次等待2秒，依此类推
        status_forcelist=[500, 502, 503, 504],  # 针对这些HTTP状态码进行重试
        allowed_methods=["POST"]  # 仅对POST请求进行重试
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

session = create_session()

def fetch_pull_requests(query, variables):
    payload = {
        'query': query,
        'variables': variables
    }
    try:
        response = session.post(GITHUB_GRAPHQL_URL, json=payload, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 502:
            print("Bad Gateway. Retrying...")
            return None
        else:
            print(f"Request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {e}")
        return None

def get_pull_requests(search_query, first=100, after=None):
    variables = {
        "searchQuery": search_query,
        "first": first,
        "after": after
    }
    data = fetch_pull_requests(QUERY, variables)
    if data and 'errors' not in data:
        return data['data']  # 返回整个 data 对象，包括 'search' 和 'rateLimit'
    elif data and 'errors' in data:
        for error in data['errors']:
            print(f"GraphQL Error: {error['message']}")
    return None


def split_time_range(start_date, end_date, granularity='month'):
    """
    将时间范围按月分割
    """
    ranges = []
    current_start = start_date
    while current_start < end_date:
        if granularity == 'month':
            # 计算下一个月的第一天
            if current_start.month == 12:
                next_month = datetime.datetime(current_start.year + 1, 1, 1)
            else:
                next_month = datetime.datetime(current_start.year, current_start.month + 1, 1)
        elif granularity == 'week':
            next_month = current_start + datetime.timedelta(weeks=1)
        else:
            raise ValueError("Unsupported granularity")
        
        current_end = min(next_month, end_date)
        ranges.append((current_start, current_end))
        current_start = current_end
    return ranges

def construct_search_query(base_query, start_date, end_date):
    """
    构建带有时间范围过滤的搜索查询
    """
    # GitHub 搜索语法，使用 merged:YYYY-MM-DD..YYYY-MM-DD
    merged_query = f'merged:{start_date.strftime("%Y-%m-%d")}..{(end_date - datetime.timedelta(days=1)).strftime("%Y-%m-%d")}'
    full_query = f'{base_query} {merged_query}'
    return full_query

def recursive_fetch(base_query, start_date, end_date, pull_requests, max_per_query=1000):
    """
    递归地分割时间范围并获取 Pull Requests
    """
    search_query = construct_search_query(base_query, start_date, end_date)
    print(f"Searching: {search_query}")
    
    # 初始查询，获取 issueCount 和 rateLimit
    data = get_pull_requests(search_query, first=1)  # 先获取 issueCount
    if not data:
        return
    
    issue_count = data['search']['issueCount']
    rate_limit = data.get('rateLimit', {})
    remaining = rate_limit.get('remaining')
    reset_at = rate_limit.get('resetAt')
    # 解析 reset_at 并转换为上海时间
    reset_time_utc = parser.isoparse(reset_at)
    reset_time_shanghai = reset_time_utc.astimezone(ZoneInfo("Asia/Shanghai"))

    print(f"Found {issue_count} PRs in range {start_date.date()} to {end_date.date()}")
    print(f"Rate Limit: {remaining} remaining, resets at {reset_time_shanghai}")

    if remaining < 100:  # 当剩余次数少于100时，等待直到重置
        if reset_at:
            try:
                print(f"Rate Limit resets at {reset_time_shanghai} (Shanghai Time)")
                # 计算等待时间
                reset_timestamp = reset_time_utc.timestamp()
                current_timestamp = time.time()
                sleep_time = reset_timestamp - current_timestamp + 10  # 加10秒的缓冲
                if sleep_time > 0:
                    print(f"Rate limit approaching. Sleeping for {sleep_time} seconds...")
                    time.sleep(sleep_time)
            except Exception as e:
                print(f"Error parsing reset_at: {e}. Sleeping for 60 seconds as fallback.")
                time.sleep(60)
        else:
            print("Rate limit approaching but 'resetAt' is None. Sleeping for 60 seconds as fallback.")
            time.sleep(60)
    
    if issue_count == 0:
        return
    elif issue_count > max_per_query:
        # 超过最大限制，进一步分割
        if start_date >= end_date:
            print("Cannot split further.")
            return
        sub_ranges = split_time_range(start_date, end_date)
        for sub_start, sub_end in sub_ranges:
            recursive_fetch(base_query, sub_start, sub_end, pull_requests, max_per_query)
    else:
        # 获取所有数据
        cursor = None
        while True:
            variables = {
                "searchQuery": search_query,
                "first": 100,
                "after": cursor
            }
            data = fetch_pull_requests(QUERY, variables)
            if not data or 'errors' in data:
                if data and 'errors' in data:
                    for error in data['errors']:
                        print(f"GraphQL Error: {error['message']}")
                break
            
            # 处理 rateLimit 信息
            rate_limit = data.get('data', {}).get('rateLimit', {})
            remaining = rate_limit.get('remaining', 0)
            reset_at = rate_limit.get('resetAt')
            # 解析 reset_at 并转换为上海时间
            reset_time_utc = parser.isoparse(reset_at)
            reset_time_shanghai = reset_time_utc.astimezone(ZoneInfo("Asia/Shanghai"))
            print(f"Rate Limit: {remaining} remaining, resets at {reset_time_shanghai}")
            
            if remaining < 100:
                reset_time = parser.isoparse(reset_time_shanghai).timestamp()
                current_time = time.time()
                sleep_time = reset_time - current_time + 10  # 加10秒的缓冲
                if sleep_time > 0:
                    print(f"Rate limit approaching. Sleeping for {sleep_time} seconds...")
                    time.sleep(sleep_time)
            
            edges = data['data']['search']['edges']
            for edge in edges:
                pr = edge['node']
                pull_requests.append({
                    'title': pr['title'],
                    'url': pr['url'],
                    'createdAt': pr['createdAt'],
                    'mergedAt': pr['mergedAt'],
                    'number': pr['number'],
                    'author': pr['author']['login'] if pr['author'] else None,
                    'baseRefName': pr['baseRefName'],
                    'headRefName': pr['headRefName']
                })
            
            page_info = data['data']['search']['pageInfo']
            if page_info['hasNextPage']:
                cursor = page_info['endCursor']
            else:
                break

def get_all_pull_requests_over_1000(base_query, overall_start_date, overall_end_date):
    """
    获取超过1000条的 Pull Requests
    """
    pull_requests = []
    recursive_fetch(base_query, overall_start_date, overall_end_date, pull_requests)
    return pull_requests

def load_existing_pull_requests(file_path):
    """
    读取已存在的 Pull Requests 数据
    """
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                existing_prs = json.load(f)
                print(f"Loaded {len(existing_prs)} existing Pull Requests from '{file_path}'.")
                return existing_prs
            except json.JSONDecodeError:
                print(f"File '{file_path}' is empty or contains invalid JSON. Starting with an empty list.")
                return []
    else:
        print(f"File '{file_path}' does not exist. Starting with an empty list.")
        return []

def save_pull_requests(file_path, pull_requests):
    """
    保存 Pull Requests 数据到文件
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(pull_requests, f, ensure_ascii=False, indent=2)
    print(f"Pull Requests have been saved to '{file_path}'.")

def merge_pull_requests(existing_prs, new_prs):
    """
    合并现有的 PR 数据和新的 PR 数据，避免重复。
    基于 PR 的 'number' 字段进行去重（假设在同一仓库内唯一）。
    """
    # 使用字典以 'number' 为键，实现快速去重
    prs_dict = {pr['url']: pr for pr in existing_prs}
    for pr in new_prs:
        prs_dict[pr['url']] = pr  # 如果存在相同的 'number'，将被新的 PR 覆盖
    
    combined_prs = list(prs_dict.values())
    print(f"Total Pull Requests after merging: {len(combined_prs)}")
    return combined_prs

if __name__ == "__main__":
    # 定义你的搜索基础查询
    base_query = 'feat "test plan" is:pr language:Python is:merged'
    
    # 定义查询的整体时间范围
    # 例如，从 2020-01-01 到 2024-12-31
    overall_start_date = datetime.datetime(2020, 1, 1)
    overall_end_date = datetime.datetime(2024, 12, 31)
    
    # 定义存储文件路径
    file_path = 'pull_requests.json'
    
    # 读取已存在的 Pull Requests
    existing_prs = load_existing_pull_requests(file_path)
    
    # 获取所有新的 Pull Requests
    all_prs = get_all_pull_requests_over_1000(base_query, overall_start_date, overall_end_date)
    
    print(f"Total Pull Requests fetched: {len(all_prs)}")
    
    # 合并现有的 PR 数据与新的 PR 数据
    combined_prs = merge_pull_requests(existing_prs, all_prs)
    
    # 保存合并后的 PR 数据到文件
    save_pull_requests(file_path, combined_prs)
