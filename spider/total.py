from lxml import etree
import re
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urlparse


def one_url():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    c = set()
    for i in range(1, 2): #此处范围为第几页到第几页
        url = f"https://github.com/search?q=feat+%22test+plan%22+language%3APython+&type=pullrequests&p={i}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            resp.encoding = 'utf-8'
            tree = etree.HTML(resp.text)
            nodes1 = tree.xpath(f"/html/body/div[1]//a[@class]/@href")
            pattern = r'^/.+/\w+/\w+/\d+'
            matched_strings = [s for s in nodes1 if re.search(pattern, s)]
            truncated_strings = [re.sub(r'/\d+$', '', s) for s in matched_strings]
            truncated_strings = set(truncated_strings)
            for x in truncated_strings:
                c.add(r'https://github.com/' + x + "s?q=feat+%22test+plan%22+is%3Apr+is%3Amerged+")
    return c


def need_url(set1, x):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
    }
    url = x
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        resp.encoding = 'utf-8'
        # print(resp.text)
        tree = etree.HTML(resp.text)
        nodes1 = tree.xpath(f"//a[@class]/@href")
        pattern = r'^/.+/\w+/\w+/\d+$'
        matched_strings = [s for s in nodes1 if re.search(pattern, s)]
        matched_strings = set(matched_strings)
        for y in matched_strings:
            set1.add(r'https://github.com/' + y)


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
        return {"error": f"Failed to get PR {pr_number} commits. Status code: {response.status_code}",
                "details": response.json()}


def get_pull_request_commits_sha(owner, repo, sha, token):
    # GitHub API URL to get a pull request
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"

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


def get_code(code_url, token):
    # GitHub API URL to get a pull request
    url = code_url

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


def get_allcode(code_url, token):
    # GitHub API URL to get a pull request
    url = code_url

    # Headers to authenticate the request
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }

    # Send GET request to GitHub API
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    return soup


def extract_info_from_pr(url):

    response = requests.get(url)
    if response.status_code!= 200:
        print(f"请求失败，状态码: {response.status_code}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    info = {
        "项目名称": [],
        "项目star": [],
        "项目网址": url,
        "pr的文本描述": [],
        "增加的代码": [],
        "删减的代码": [],
        "最后的完整代码": []
    }

    # 获取url的基本信息：
    #token为密钥固定的
    token = "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"  # Replace with your GitHub personal access token
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    owner = path_parts[2]
    repo = path_parts[3]
    pr_number = int(path_parts[5])
    info["项目名称"] = owner

    # 获取项目star
    url2 = f"https://github.com/{owner}/{repo}"
    response = requests.get(url2)
    soup = BeautifulSoup(response.text, 'html.parser')
    # 查找包含数字的span元素
    span = soup.find('span', id='repo-stars-counter-star')
    if span:
        number = span['title'].replace(',', '')
    info["项目star"] = number

    # 获取pr的文本描述
    headers = {
        'Authorization': f'token {token}',  # Use the GitHub token for authentication
        'Accept': 'application/vnd.github.v3+json',  # Ensure we're using the right API version
    }
    url1 = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    response = requests.get(url1, headers=headers)
    if response.status_code == 200:
        # Successfully fetched the PR details
        data = response.json()
        info["pr的文本描述"] = str(data['body'])

    #获取代码变更及完整代码
    url = url+"/files"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"请求失败，状态码: {response.status_code}")
        return {}
    soup = BeautifulSoup(response.text, 'html.parser')
    rows = soup.find_all('tr')  # 这里我们假设只有一个<tr>，或者我们想要处理所有<tr>
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
    #完整代码
    commit_details = get_pull_request_commits(owner, repo, pr_number, token)
    # 获取sha
    first_commit = commit_details[0] if commit_details else None
    sha = first_commit["sha"]
    commit_details = get_pull_request_commits_sha(owner, repo, sha, token)
    # 获取code_url
    code_url = commit_details["files"][0]["contents_url"]
    code = get_code(code_url, token)
    # 获取code_url_download
    code_url = code
    code_url_download = code_url["download_url"]
    all_code = get_allcode(code_url_download,token)
    info["最后的完整代码"] = str(all_code)

    return info


def main():
    set1 = set()
    one_urls = one_url()
    for x in one_urls:
        need_url(set1, x)
    b = 1
    for url in set1:
        print(f"第{b}个pull request")
        result = extract_info_from_pr(url)
        json_result = json.dumps(result, ensure_ascii=False, indent=4)
        print(json_result)
        b += 1
        print()

main()
# 第16行设置页数的范围
