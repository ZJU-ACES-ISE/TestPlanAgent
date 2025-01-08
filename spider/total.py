from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse
import random
import ast
from zoneinfo import ZoneInfo
import requests
import datetime
from dateutil import parser
from dotenv import load_dotenv
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def input_proxies():
    proxies_list = []
    try:
        with open('proxies.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    proxies_list.append(line)
    except FileNotFoundError:
        print('proxies.txt文件未找到')
    return proxies_list


def get_pull_request_commits(owner, repo, pr_number, token):
    # GitHub API URL to get a pull request
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"

    # Headers to authenticate the request
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }

    # Send GET request to GitHub API
    proxies_list = input_proxies()
    num = random.randint(0, len(proxies_list) - 1)
    try:
        proxies = ast.literal_eval(proxies_list[num])
    except (SyntaxError, ValueError) as e:
        print(f"解析代理字符串时发生错误: {e}，跳过此代理...")
        return None
    response = requests.get(url=url, headers=headers, proxies=proxies)
    if response.status_code == 200:
        return response.json()


def get_pull_request_commits_sha(owner, repo, sha, token):
    # GitHub API URL to get a pull request
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"

    # Headers to authenticate the request
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }

    # Send GET request to GitHub API
    proxies_list = input_proxies()
    num = random.randint(0, len(proxies_list) - 1)
    try:
        proxies = ast.literal_eval(proxies_list[num])
    except (SyntaxError, ValueError) as e:
        print(f"解析代理字符串时发生错误: {e}，跳过此代理...")
        return None
    response = requests.get(url=url, headers=headers, proxies=proxies)
    if response.status_code == 200:
        return response.json()


def get_code(code_url, token):
    # GitHub API URL to get a pull request
    url = code_url

    # Headers to authenticate the request
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }

    # Send GET request to GitHub API
    proxies_list = input_proxies()
    num = random.randint(0, len(proxies_list) - 1)
    try:
        proxies = ast.literal_eval(proxies_list[num])
    except (SyntaxError, ValueError) as e:
        print(f"解析代理字符串时发生错误: {e}，跳过此代理...")
        return None
    response = requests.get(url=url, headers=headers, proxies=proxies)
    if response.status_code == 200:
        return response.json()


def get_allcode(code_url, token):
    # GitHub API URL to get a pull request
    url = code_url

    # Headers to authenticate the request
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }

    # Send GET request to GitHub API
    proxies_list = input_proxies()
    num = random.randint(0, len(proxies_list) - 1)
    try:
        proxies = ast.literal_eval(proxies_list[num])
    except (SyntaxError, ValueError) as e:
        print(f"解析代理字符串时发生错误: {e}，跳过此代理...")
        return None
    response = requests.get(url=url, headers=headers, proxies=proxies)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup


def extract_info_from_pr(url, b):
    info = {
        "项目名称": [],
        "项目star": [],
        "项目网址": url,
        "pr的文本描述": [],
        "增加的代码": [],
        "删减的代码": [],
        "最后的完整代码": []
    }

    token_list = [
        "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",
        "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",
        "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",
        "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",
        "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",
        "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",
        "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"
    ]

    b = b % 7
    token = token_list[b]

    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    owner = path_parts[1]
    repo = path_parts[2]
    pr_number = int(path_parts[4])
    info["项目名称"] = repo

    # 获取项目star
    url2 = f"https://github.com/{owner}/{repo}"
    response = requests.get(url2)
    soup = BeautifulSoup(response.text, 'html.parser')
    span = soup.find('span', id='repo-stars-counter-star')
    if span:
        number = span['title'].replace(',', '')
        info["项目star"] = number

    # 获取pr的文本描述
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    url1 = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(url1, headers=headers)
    if response.status_code == 200:
        data = response.json()
        info["pr的文本描述"] = str(data['body'])

    # 获取代码变更及完整代码
    url = url + "/files"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    rows = soup.find_all('tr')
    for row in rows:
        code_td = row.find('td', class_='blob-code-addition')
        if code_td:
            code = code_td.get_text(strip=True)
            info["增加的代码"].append(code)
    for row in rows:
        code_td = row.find('td', class_='blob-code-deletion')
        if code_td:
            code = code_td.get_text(strip=True)
            info["删减的代码"].append(code)

    # 完整代码
    commit_details = get_pull_request_commits(owner, repo, pr_number, token)
    if commit_details:
        first_commit = commit_details[0]
        sha = first_commit["sha"]
        commit_details = get_pull_request_commits_sha(owner, repo, sha, token)
        if commit_details:
            code_url = commit_details["files"][0]["contents_url"]
            code = get_code(code_url, token)
            if code:
                code_url = code
                code_url_download = code_url["download_url"]
                all_code = get_allcode(code_url_download, token)
                info["最后的完整代码"] = str(all_code)
    return info


def pr_list():
    # 加载 .env 文件
    load_dotenv()

    # 读取 GitHub Token
    token = "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"

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
        # print(f"Searching: {search_query}")

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

        # print(f"Found {issue_count} PRs in range {start_date.date()} to {end_date.date()}")
        # print(f"Rate Limit: {remaining} remaining, resets at {reset_time_shanghai}")

        if remaining < 100:  # 当剩余次数少于100时，等待直到重置
            if reset_at:
                try:
                    # print(f"Rate Limit resets at {reset_time_shanghai} (Shanghai Time)")
                    # 计算等待时间
                    reset_timestamp = reset_time_utc.timestamp()
                    current_timestamp = time.time()
                    sleep_time = reset_timestamp - current_timestamp + 10  # 加10秒的缓冲
                    if sleep_time > 0:
                        # print(f"Rate limit approaching. Sleeping for {sleep_time} seconds...")
                        time.sleep(sleep_time)
                except Exception as e:
                    print(f"Error parsing reset_at: {e}. Sleeping for 60 seconds as fallback.")
                    time.sleep(60)
            else:
                # print("Rate limit approaching but 'resetAt' is None. Sleeping for 60 seconds as fallback.")
                time.sleep(60)

        if issue_count == 0:
            return
        elif issue_count > max_per_query:
            # 超过最大限制，进一步分割
            if start_date >= end_date:
                # print("Cannot split further.")
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
                # print(f"Rate Limit: {remaining} remaining, resets at {reset_time_shanghai}")

                if remaining < 100:
                    reset_time = parser.isoparse(reset_time_shanghai).timestamp()
                    current_time = time.time()
                    sleep_time = reset_time - current_time + 10  # 加10秒的缓冲
                    if sleep_time > 0:
                        # print(f"Rate limit approaching. Sleeping for {sleep_time} seconds...")
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

    # 定义你的搜索基础查询
    base_query = 'feat "test plan" is:pr language:Python is:merged'

    # 定义查询的整体时间范围
    # 例如，从 2020-01-01 到 2024-12-31
    overall_start_date = datetime.datetime(2020, 1, 1)
    overall_end_date = datetime.datetime(2024, 12, 31)

    # 获取所有新的 Pull Requests
    all_prs = get_all_pull_requests_over_1000(base_query, overall_start_date, overall_end_date)
    print(f"Total Pull Requests fetched: {len(all_prs)}")
    return all_prs


def save_pull_requests(file_path, pull_requests):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(pull_requests, f, ensure_ascii=False, indent=2)
    print(f"Pull Requests have been saved to '{file_path}'.")


if __name__ == "__main__":
    b = 1
    data = pr_list()
    ans = 0
    pull_requests_list = []
    # 遍历数据列表，打印每个URL
    for item in data:
        while ans == 0:
            url = item['url']
            print(url)
            print(f"第{b}个pull request")
            try:
                result = extract_info_from_pr(url, b)
                json_result = json.dumps(result, ensure_ascii=False, indent=4)
                pull_requests_list.append(json_result)
                ans = 1
            except Exception as e:
                print(f"处理第{b}个pull request时发生异常: {e}")
        ans = 0
        b += 1
        print()

    file_path = 'pull_requests.json'
    save_pull_requests(file_path, pull_requests_list)
