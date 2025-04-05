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
    }
]

class LLMClassifier:
    """使用LLM进行GitHub评论意图分类"""
    
    def __init__(self, api_key, model_name="gpt-4o-mini", temperature=0.0):
        """
        初始化分类器
        
        参数:
        api_key (str): API密钥
        model_name (str): 模型名称
        temperature (float): 温度参数，控制输出随机性
        """
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.categories = CATEGORIES
        self.prompt_template = self._create_prompt_template()

    def _get_category_explanation(self, category):
        """获取类别的详细解释"""
        explanations = {
            1: "Share knowledge and experience with other people, or inform other people about new plans/updates.",
            2: "Attempt to obtain information or help from other people.",
            3: "Require to improve existing features or implement new features.",
            4: "Share possible solutions for discovered problems.",
            5: "Report bugs, or describe unexpected behaviors.",
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
            You are a professional code review comment intent identifier. Please analyze the following GitHub code review comments and place them in one of the 7 categories below:

            {category_descriptions}

            Here are some examples of categorization:

            {examples}

            Comment: 
            
            {{comment}}

            Return only the corresponding numeric label (1-7) without any additional explanation.

            categorization:
        """
        
        return template


    
    def classify_comment(self, comment):
        """
        使用LLM对单个评论进行分类
        
        参数:
        comment (str): 需要分类的GitHub评论
        
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
        
        try:
            response = requests.post(
                "https://api.gptsapi.net/v1/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result["choices"][0]["message"]["content"].strip()
            
            # 提取分类结果（数字）
            try:
                # 尝试直接解析数字
                classification = int(response_text)
                # 确保在有效范围内
                if classification < 1 or classification > 13:
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
                
        except Exception as e:
            print(f"API调用错误: {e}")
            return None
    
    def batch_classify(self, comments, batch_size=10, sleep_time=0.1):
        """
        批量分类评论
        
        参数:
        comments (list): 评论列表
        batch_size (int): 批处理大小,防止API限制
        
        返回:
        list: 分类结果列表
        """
        results = []
        
        for comment in comments:
            classification = self.classify_comment(comment)
            results.append(classification)
                
        return results

def main():
    """主函数"""
    # 设置API密钥
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("请设置OPENAI_API_KEY环境变量")
    
    # 初始化分类器
    classifier = LLMClassifier(api_key=api_key)
   
    # 分类评论
    print("开始分类...")

    with open('data/pre_processed_pr_full_comments.json', 'r') as f:
        pr_total_comments = json.load(f)

    for project_name in tqdm(pr_total_comments):
        for pr_number in tqdm(pr_total_comments[project_name]):
            pr_comments = pr_total_comments[project_name][pr_number]
            pr_contents = classifier.batch_classify(pr_comments)

            pr_total_comments[project_name][pr_number] = {}
            if pr_contents.count(5) > 0:
                pr_total_comments[project_name][pr_number]["PR_content"] = "negative"
            else:
                pr_total_comments[project_name][pr_number]["PR_content"] = "positive"
            pr_comments_and_content = []
            for text, content in zip(pr_comments, pr_contents):
                pr_comments_and_content.append({"comment": text, "content": content})

            pr_total_comments[project_name][pr_number]["comments"] = pr_comments_and_content
    with open('data/pre_processed_contraction_pr_full_comments_sentiment_gpt-4o.json', 'w') as f:
        json.dump(pr_total_comments, f)


if __name__ == "__main__":
    main()