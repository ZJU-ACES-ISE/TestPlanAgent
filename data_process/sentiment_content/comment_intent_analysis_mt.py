import os
import json
import time
import pandas as pd
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, classification_report, confusion_matrix
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
import threading
import concurrent.futures
from queue import Queue

# 定义分类标签
CATEGORIES = {
    1: "information giving",
    2: "information seeking",
    3: "feature request",
    4: "solution proposal",
    5: "problem discovery",
    6: "aspect evaluation",
    7: "others"
}

# 少量示例(Few-Shot Examples)
FEW_SHOT_EXAMPLES = [
    {
        "comment": "The typeahead from Bootstrap v2 was removed.",
        "label": 1  
    },
    {
        "comment": "Are there any developers working on it?",
        "label": 2 
    },
    {
        "comment": "Please add a titled panel component to Twitter Bootstrap.",
        "label": 3  
    },
    {
        "comment": "I fixed this for UI Kit using the following CSS.",
        "label": 4  
    },
    {
        "comment": "the firstletter issue was causing a crash.",
        "label": 5  
    },
    {
        "comment": "I think BS3's new theme looks good, it's a little flat style.",
        "label": 6  
    },
    {
        "comment": "Thanks for the feedback!",
        "label": 7  
    },
    {
        "comment": "We should add error handling for this case.",
        "label": 3
    },
    {
        "comment": "The code could throw an exception if the input is null.",
        "label": 6
    }
]

class LLMClassifier:
    """使用LLM进行GitHub评论意图分类"""
    
    def __init__(self, api_key, model_name="gpt-4o", temperature=0.0, max_workers=5):
        """
        初始化分类器
        
        参数:
        api_key (str): API密钥
        model_name (str): 模型名称
        temperature (float): 温度参数，控制输出随机性
        max_workers (int): 最大工作线程数
        """
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.categories = CATEGORIES
        self.prompt_template = self._create_prompt_template()
        self.max_workers = max_workers

    def _get_category_explanation(self, category):
        """获取类别的详细解释"""
        explanations = {
            1: "Share knowledge and experience with other people, or inform other people about new plans/updates.",
            2: "Attempt to obtain information, help, or clarification from other people; express confusion about code behavior or questioning why something works/doesn't work in a certain way.",
            3: "Require to improve existing features or implement new features.",
            4: "Share possible solutions for discovered problems.",
            5: "Report bugs, describe encountered errors, or mention failures during execution, testing, or usage.",
            6: "Express opinions or evaluations on a specific aspect.",
            7: "Sentences with little meaning or importance.",
        }
        return explanations.get(category, "")

    def _create_prompt_template(self):
        """创建分类提示模板"""

        # 构建类别描述
        category_descriptions = "\n".join([
            f"{k}: {v} - {self._get_category_explanation(k)}" 
            for k, v in self.categories.items()
        ])
        
        # 构建Few-Shot示例
        examples = "\n\n".join([
            f"comment: {example['comment']}\ncategorization: {example['label']} ({self.categories[example['label']]})"
            for example in FEW_SHOT_EXAMPLES
        ])
        
        # 完整提示
        template = f"""
            You are a professional code review comment intent identifier specializing in detecting error-related feedback. Please analyze the following GitHub code review comments and place them in one of the 7 categories below:

            {category_descriptions}

            Important note: Please exercise caution when categorizing "problem discovery" (5). Only classify comments as category 5 when they explicitly describe specific errors that have been encountered or discovered (such as crashes, exceptions, compilation errors, malfunctions, etc.). If the comment expresses confusion, questions, or seeks explanation about code behavior, even if it implies potential issues, it should be classified as "information seeking" (2). Be careful to distinguish between "I found this error" (category 5) and "This behavior is confusing, is there a problem?" (category 2).

            Here are some examples of categorization:

            {examples}

            Comment: 
            
            {{comment}}

            Return only the corresponding numeric label (1-7) without any additional explanation.

            categorization:
        """
        
        return template

    def classify_comment(self, comment, max_retries=3, retry_delay=1):
        """
        使用LLM对单个评论进行分类，带有重传机制
        
        参数:
        comment (str): 需要分类的GitHub评论
        max_retries (int): 最大重试次数
        retry_delay (int): 重试间隔时间(秒)
        
        返回:
        int: 分类标签(1-7)
        """
        prompt = self.prompt_template.format(comment=comment)
        
        # 调用Anthropic Claude API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-type": "application/json"
        }
        
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": self.temperature
        }
        
        # 重传机制
        retries = 0
        while retries <= max_retries:
            try:
                response = requests.post(
                    # "https://api.gptsapi.net/v1/messages",
                    "https://api.gptsapi.net/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30  # 添加超时设置
                )
                response.raise_for_status()
                
                result = response.json()
                response_text = result["choices"][0]["message"]["content"].strip()
                # response_text = result["content"][0]["text"].strip()
                # 提取分类结果（数字）
                try:
                    # 尝试直接解析数字
                    classification = int(response_text)
                    # 确保在有效范围内
                    if classification < 1 or classification > 7:
                        return None
                    return classification
                except ValueError:
                    # 如果直接解析失败，尝试从文本中提取数字
                    import re
                    match = re.search(r'\b(1[0-3]|[1-9])\b', response_text)
                    if match:
                        return int(match.group(1))
                    print(f"无法解析分类结果：{comment}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                # 网络错误或API错误，准备重试
                retries += 1
                wait_time = retry_delay * (2 ** (retries - 1))  # 指数退避策略
                print(f"API请求失败 (尝试 {retries}/{max_retries}): {e}，将在 {wait_time} 秒后重试...")
                time.sleep(wait_time)
                continue
            except Exception as e:
                # 其他非网络错误
                print(f"处理API响应时出错: {e}")
                return None
        
        # 达到最大重试次数后仍失败
        print(f"达到最大重试次数 ({max_retries})，API请求失败")
        return None
    
    def worker(self, comment_queue, result_dict, lock):
        """工作线程函数"""
        while not comment_queue.empty():
            try:
                idx, comment = comment_queue.get(block=False)
                classification = self.classify_comment(comment)
                
                # 安全地更新结果字典
                with lock:
                    result_dict[idx] = classification
                
                # 处理完成一个任务
                comment_queue.task_done()
                
                # 防止API速率限制，稍微暂停
                time.sleep(0.1)
            except Exception as e:
                print(f"工作线程错误: {e}")
    
    def batch_classify(self, comments, batch_size=10):
        """
        使用多线程批量分类评论
        
        参数:
        comments (list): 评论列表
        batch_size (int): 批处理大小，用于进度展示
        
        返回:
        list: 分类结果列表
        """
        # 结果存储和线程同步
        result_dict = {}
        comment_queue = Queue()
        lock = threading.Lock()
        
        # 将所有评论放入队列
        for idx, comment in enumerate(comments):
            comment_queue.put((idx, comment))
        
        # 创建并启动工作线程
        total_task_count = len(comments)
        workers = []
        
        for _ in range(min(self.max_workers, total_task_count)):
            thread = threading.Thread(
                target=self.worker,
                args=(comment_queue, result_dict, lock)
            )
            thread.daemon = True
            thread.start()
            workers.append(thread)
        
        # 使用tqdm显示进度
        with tqdm(total=total_task_count) as pbar:
            prev_done = 0
            while not comment_queue.empty():
                current_done = total_task_count - comment_queue.qsize()
                if current_done > prev_done:
                    pbar.update(current_done - prev_done)
                    prev_done = current_done
                time.sleep(0.1)
        
        # 等待所有任务完成
        comment_queue.join()
        
        # 将结果字典转换为列表
        results = [result_dict.get(i) for i in range(len(comments))]
        return results
    
    def concurrent_batch_classify(self, comments):
        """
        使用concurrent.futures进行并发批量分类（替代方案）
        
        参数:
        comments (list): 评论列表
        
        返回:
        list: 分类结果列表
        """
        results = [None] * len(comments)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 创建未来任务映射
            future_to_index = {
                executor.submit(self.classify_comment, comment): i 
                for i, comment in enumerate(comments)
            }
            
            # 处理完成的任务，使用tqdm显示进度
            for future in tqdm(concurrent.futures.as_completed(future_to_index), total=len(comments)):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    print(f"任务执行错误 (index={index}): {e}")
        
        return results


# def main():
#     """主函数"""
#     # 设置API密钥
#     api_key = os.environ.get("OPENAI_API_KEY")
#     # api_key = "sk-Y9Ba7ca3cb6235a6b6f2d371c3bc11db13f0a1e8bf9a4p5o"
#     if not api_key:
#         raise ValueError("请设置OPENAI_API_KEY环境变量")
    
#     # 初始化分类器（设置合适的工作线程数）
#     classifier = LLMClassifier(api_key=api_key, max_workers=10)
   
#     # 分类评论
#     print("开始分类...")

#     # 加载数据
#     with open('data/comments/pre_processed_pr_full_comments_add_reviews.json', 'r') as f:
#         pr_total_comments = json.load(f)

#     # 处理每个项目和PR
#     for project_name in tqdm(pr_total_comments):
#         for pr_number in tqdm(pr_total_comments[project_name]):
#             pr_comments = pr_total_comments[project_name][pr_number]
            
#             # 使用多线程批量分类
#             # 选择其中一种多线程方法
#             # pr_contents = classifier.batch_classify(pr_comments)
#             pr_intents = classifier.concurrent_batch_classify(pr_comments)

#             # 处理分类结果
#             pr_total_comments[project_name][pr_number] = {}
#             if pr_intents.count(5) > 0:
#                 pr_total_comments[project_name][pr_number]["PR_intent"] = "negative"
#             else:
#                 pr_total_comments[project_name][pr_number]["PR_intent"] = "positive"
            
#             # 组合评论和分类结果
#             pr_comments_and_intent = []
#             for text, intent in zip(pr_comments, pr_intents):
#                 pr_comments_and_intent.append({"comment": text, "intent": intent})

#             pr_total_comments[project_name][pr_number]["comments"] = pr_comments_and_intent

#     # 保存结果
#     with open('data/sentiment_intent/pre_processed_contraction_pr_full_comments_sentiment_gpt-4o_threaded_3.json', 'w') as f:
#         json.dump(pr_total_comments, f)

def test_one_comment():
    # 设置API密钥
    api_key = os.environ.get("OPENAI_API_KEY")
    # api_key = "sk-Y9Ba7ca3cb6235a6b6f2d371c3bc11db13f0a1e8bf9a4p5o"
    if not api_key:
        raise ValueError("请设置OPENAI_API_KEY环境变量")
    
    comment = ["@nisanthannanthakumar it would. but the timeout will error out when codeblock is called so it should never get to that line."]

    # 初始化分类器（设置合适的工作线程数）
    classifier = LLMClassifier(api_key=api_key, max_workers=10)
    pr_intent = classifier.concurrent_batch_classify(comment)
    print(pr_intent)
if __name__ == "__main__":
    test_one_comment()