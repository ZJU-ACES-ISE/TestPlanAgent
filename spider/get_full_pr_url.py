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
    page = 1
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