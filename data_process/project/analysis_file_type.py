import json
import os
import requests
import re
import time
import concurrent.futures
from collections import Counter
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def create_session_with_retries(retries=3, backoff_factor=0.3, 
                               status_forcelist=(500, 502, 504)):
    """创建一个带有重试机制的会话"""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def extract_repo_and_pr_number(pr_url):
    """从PR URL中提取仓库名和PR编号"""
    # 解析URL路径
    path = urlparse(pr_url).path
    # 分割路径部分
    parts = path.strip('/').split('/')
    
    if len(parts) >= 4 and parts[2] == 'pull':
        owner = parts[0]
        repo = parts[1]
        pr_number = parts[3]
        return f"{owner}/{repo}", pr_number
    
    return None, None

def get_pr_files(repo, pr_number, session=None, max_retries=3):
    """获取PR中的文件列表，带有重试机制"""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
    token = "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"
    headers = {
        'Authorization': f'token {token}',  
        'Accept': 'application/vnd.github.v3+json',
    }
    
    if session is None:
        session = create_session_with_retries(retries=max_retries)
    
    try:
        response = session.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"获取文件失败: {repo}/{pr_number}, 错误: {e}")
        return []

def analyze_file_types(files):
    """分析文件类型"""
    file_types = []
    
    for file in files:
        filename = file['filename']
        # 提取文件扩展名
        extension = filename.split('.')[-1] if '.' in filename else 'no_extension'
        file_types.append(extension)
    
    return Counter(file_types)

def process_pr(pr_url, session=None):
    """处理单个PR的函数，用于多线程执行"""
    repo, pr_number = extract_repo_and_pr_number(pr_url)
    result = {
        'pr_url': pr_url,
        'repo': repo,
        'pr_number': pr_number,
        'files': [],
        'file_types': Counter(),
        'success': False
    }
    
    if repo and pr_number:
        files = get_pr_files(repo, pr_number, session)
        
        if files:
            result['files'] = files
            result['file_types'] = analyze_file_types(files)
            result['success'] = True
    
    return result

def main():
    # 创建一个带重试机制的会话，所有线程共享
    session = create_session_with_retries(retries=3)
    
    # 加载PR URL数据
    with open("data/PR/PR_URL_for_test_true.json", "r") as f:
        PR_data = json.load(f)
    
    pr_urls = []
    for project in PR_data:
        pr_urls.extend(PR_data[project])
    new_pr_urls = []
    for pr in pr_urls:
        new_pr_urls.append("https://" + pr.split("https://")[1])
    pr_urls = new_pr_urls
    # 创建一个全局的文件类型计数器
    all_file_types = Counter()
    total_files = 0
    processed_prs = 0
    failed_prs = 0
    
    # 使用线程池来并行处理PR
    max_workers = min(32, len(pr_urls))  # 根据PR数量调整线程数，最多32个
    print(f"启动多线程处理，线程数: {max_workers}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务到线程池
        future_to_url = {executor.submit(process_pr, url, session): url for url in pr_urls}
        
        # 处理结果
        for future in concurrent.futures.as_completed(future_to_url):
            pr_url = future_to_url[future]
            try:
                result = future.result()
                processed_prs += 1
                
                # 打印处理进度
                print(f"\n进度: {processed_prs}/{len(pr_urls)} - 分析PR: {pr_url}")
                
                if result['success']:
                    # 统计当前PR的文件类型
                    file_types = result['file_types']
                    files = result['files']
                    
                    print(f"文件类型统计:")
                    for ext, count in file_types.most_common():
                        print(f"  .{ext}: {count}个文件")
                    
                    # 添加到全局统计
                    all_file_types.update(file_types)
                    total_files += len(files)
                    
                    # 输出具体的文件名
                    print("\n文件列表:")
                    for file in files:
                        print(f"  {file['filename']}")
                else:
                    failed_prs += 1
                    if result['repo'] and result['pr_number']:
                        print(f"获取PR文件失败: {pr_url}")
                    else:
                        print(f"无法解析URL: {pr_url}")
            except Exception as exc:
                failed_prs += 1
                print(f"处理PR时出错: {pr_url}, 错误: {exc}")
    
    # 输出总体统计信息
    print("\n==================")
    print("所有PR文件类型总体统计:")
    print(f"总文件数: {total_files}")
    print(f"成功处理的PR数: {processed_prs - failed_prs}/{len(pr_urls)}")
    print(f"失败的PR数: {failed_prs}/{len(pr_urls)}")
    print("文件类型详细统计:")
    for ext, count in all_file_types.most_common():
        percentage = (count / total_files) * 100 if total_files > 0 else 0
        print(f"  .{ext}: {count}个文件 ({percentage:.2f}%)")

if __name__ == "__main__":
    start_time = time.time()
    main()
    end_time = time.time()
    print(f"\n总运行时间: {end_time - start_time:.2f}秒")