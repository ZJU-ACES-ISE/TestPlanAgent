import requests

def new_one_url():

    # 定义请求的 URL 和查询参数
    api_url = "https://api.github.com/search/issues"
    params = {
        'q': 'feat "test plan" language:Python type:pr',
        'per_page': 100 # 每页返回 100 条结果
    }

    # 定义请求头部
    headers = {
        'Authorization': 'Bearer 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',  # 个人的 GitHub token
    }

    # 初始化页码
    page = 11
    num = 0
    # 循环请求，直到没有更多的 pull request
    while True:
        # 设置当前页面
        params['page'] = page
        
        # 发送 GET 请求
        response = requests.get(api_url, headers=headers, params=params)
        
        # 检查响应状态
        if response.status_code == 200:
            data = response.json()
            pull_requests = data['items']
            for pull_reqeust in pull_requests:
                pull_request_url = pull_reqeust['url']
                num += 1
                print(pull_request_url + ':' + str(num))
            # 如果返回的结果少于 per_page，说明没有更多的数据，结束循环
            if len(pull_requests) < 100:
                break
            # 否则，继续请求下一页
            page += 1
        else:
            print(f"Request failed with status code {response.status_code}")
            break
    print(f"pages: {page}")

import requests

# GitHub GraphQL API 的 URL
url = "https://api.github.com/graphql"

# GitHub API Token
# 请确保你的 Token 具有访问仓库的必要权限
token = "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"

# GraphQL 查询，使用变量
query = """
query ($searchQuery: String!, $first: Int!, $after: String) {
  search(query: $searchQuery, type: ISSUE, first: $first, after: $after) {
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

# 定义初始变量
variables = {
    "searchQuery": 'feat "test plan" is:pr language:Python is:merged',
    "first": 100,
    "after": None  # 初始时没有游标
}

# 定义请求头部
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 发送请求
def fetch_pull_requests(query, variables):
    payload = {
        'query': query,
        'variables': variables
    }
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Request failed with status {response.status_code}")
        print(f"Response: {response.text}")
        return None

# 递归获取所有分页数据
def get_all_pull_requests(query, variables):
    pull_requests = []
    cursor = None

    while True:
        current_variables = variables.copy()
        if cursor:
            current_variables['after'] = cursor

        # 获取当前页数据
        data = fetch_pull_requests(query, current_variables)
        if not data:
            break

        # 检查是否有 GraphQL 错误
        if 'errors' in data:
            print("GraphQL Errors:")
            for error in data['errors']:
                print(error['message'])
            break

        # 获取当前页的 Pull Request 数据
        edges = data['data']['search']['edges']
        for edge in edges:
            pull_request = edge['node']
            pull_requests.append({
                'title': pull_request['title'],
                'url': pull_request['url'],
                'createdAt': pull_request['createdAt'],
                'mergedAt': pull_request['mergedAt'],
                'number': pull_request['number'],
                'author': pull_request['author']['login'],
                'baseRefName': pull_request['baseRefName'],
                'headRefName': pull_request['headRefName']
            })

        # 检查是否有下一页
        page_info = data['data']['search']['pageInfo']
        if page_info['hasNextPage']:
            cursor = page_info['endCursor']
        else:
            break

    return pull_requests

# 调用函数并打印结果
if __name__ == "__main__":
    pull_requests = get_all_pull_requests(query, variables)
    print(f"Total pull requests: {len(pull_requests)}")
    # for pr in pull_requests:
    #     print(pr)

