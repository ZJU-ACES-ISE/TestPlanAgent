"""
使用Few-Shot方法改进LLM分类器
"""

import os
import requests
import json
from sklearn.metrics import precision_score, recall_score, f1_score, classification_report
from tqdm import tqdm

# 定义分类标签
CATEGORIES = {
    1: "Readability",
    2: "Naming",
    3: "Documentation",
    4: "Error/Resource Handling",
    5: "Control Structures/Program Flow",
    6: "Visibility/Access",
    7: "Efficiency/Optimization",
    8: "Code Organization/Refactoring",
    9: "Concurrency",
    10: "High Level Method Semantics & Design",
    11: "High Level Class Semantics & Design",
    12: "Testing",
    13: "Other"
}

# 少量示例(Few-Shot Examples)
FEW_SHOT_EXAMPLES = [
    {
        "comment": "Please split this statement into two separate ones",
        "label": 1  # Readability
    },
    {
        "comment": "I think foo would be a more appropriate name",
        "label": 2  # Naming
    },
    {
        "comment": "Please add a comment here explaining this logic",
        "label": 3  # Documentation
    },
    {
        "comment": "Forgot to catch a possible exception here",
        "label": 4  # Error/Resource Handling
    },
    {
        "comment": "This if-statement should be moved after the while loop",
        "label": 5  # Control Structures/Program Flow
    },
    {
        "comment": "Make this final",
        "label": 6  # Visibility/Access
    },
    {
        "comment": "Many unnecessary calls to foo() here",
        "label": 7  # Efficiency/Optimization
    },
    {
        "comment": "Please extract this logic into a separate method",
        "label": 8  # Code Organization/Refactoring
    },
    {
        "comment": "This class does not look thread safe",
        "label": 9  # Concurrency
    },
    {
        "comment": "This method should return a String",
        "label": 10  # High Level Method Semantics & Design
    },
    {
        "comment": "This should extend Foo",
        "label": 11  # High Level Class Semantics & Design
    },
    {
        "comment": "Is there a test for this?",
        "label": 12  # Testing
    },
    {
        "comment": "Looks good, thanks!",
        "label": 13  # Other
    }
]


class ImprovedLLMClassifier:
    """使用Few-Shot方法的改进LLM分类器"""
    
    def __init__(self, api_key, model_name="gpt-4o-mini", temperature=0.0):
        """初始化分类器"""
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.categories = CATEGORIES
        
    def _create_few_shot_prompt(self, comment):
        """创建Few-Shot提示"""
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
        prompt = f"""You are a professional code review comment classifier. Please analyze the following GitHub code review comment and classify it into one of these 13 categories:

                    {category_descriptions}

                    Here are some examples of categorization:

                    {examples}

                    Return only the corresponding numeric label (1-13) without any additional explanation.

                    Comment: 
                    
                    {comment}

                    分类:
                """
        
        return prompt
    
    def _get_category_explanation(self, category):
        """获取类别的详细解释"""
        explanations = {
            1: "Comments related to readability, style, general project conventions.",
            2: "Comments related to naming.",
            3: "Comments related to licenses, package info, module documentation, commenting.",
            4: "Comments related to exception/resource handling, program failure, termination analysis, resource .",
            5: "Comments related to usage of loops, if-statements, placement of individual lines of code.",
            6: "Comments related to access level for classes, fields, methods and local variables.",
            7: "Comments related to efficiency and optimization.",
            8: "Comments related to extracting code from methods and classes, moving large chunks of code around.",
            9: "Comments related to threads, synchronization, parallelism.",
            10: "Comments relating to method design and semantics.",
            11: "Comments relating to class design and semantics.",
            12: "Comments related to testing.",
            13: "Comments not relating to categories 1-12."
        }
        return explanations.get(category, "")
    
    def classify_comment(self, comment):
        """使用Few-Shot方法分类单个评论"""
        prompt = self._create_few_shot_prompt(comment)
        
        # 调用Anthropic Claude API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-type": "application/json"
        }
        
        data = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
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
                return None
                
        except Exception as e:
            print(f"API调用错误: {e}")
            return None
    
    def compare_with_baseline(self, comments, true_labels):
        """
        比较改进的分类器与基线分类器
        
        参数:
        comments (list): 评论列表
        true_labels (list): 真实标签列表
        
        返回:
        dict: 比较结果
        """
        # 使用改进的分类器分类
        improved_predictions = []
        
        for comment in tqdm(comments):
            prediction = self.classify_comment(comment)
            improved_predictions.append(prediction)
        
        # 过滤掉None值
        valid_indices = [i for i, pred in enumerate(improved_predictions) if pred is not None]
        valid_comments = [comments[i] for i in valid_indices]
        valid_true_labels = [true_labels[i] for i in valid_indices]
        valid_improved_predictions = [improved_predictions[i] for i in valid_indices]
        
        # 计算性能指标
        improved_f1 = f1_score(valid_true_labels, valid_improved_predictions, average='macro')
        improved_precision = precision_score(valid_true_labels, valid_improved_predictions, average='macro')
        improved_recall = recall_score(valid_true_labels, valid_improved_predictions, average='macro')
        
        # 生成分类报告
        improved_report = classification_report(valid_true_labels, valid_improved_predictions, 
                                              target_names=[CATEGORIES[i] for i in sorted(CATEGORIES.keys())])
        
        return {
            'improved_f1': improved_f1,
            'improved_precision': improved_precision,
            'improved_recall': improved_recall,
            'improved_report': improved_report,
            'improved_predictions': valid_improved_predictions,
            'valid_indices': valid_indices
        }


def main():
    # 设置API密钥
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("请设置OPENAI_API_KEY环境变量")
    
    # 加载评论和标签
    with open("data/review_comments.txt", 'r', encoding='utf-8') as f:
        comments = [line.strip() for line in f.readlines()]
    comments = comments[:100]
    with open("data/review_comments_labels.txt", 'r', encoding='utf-8') as f:
        labels = [int(line.strip()) for line in f.readlines()]
    labels = labels[:100]
    # 初始化改进的分类器
    improved_classifier = ImprovedLLMClassifier(api_key)
    
    # 比较改进的分类器与基线
    comparison = improved_classifier.compare_with_baseline(comments, labels)
    
    # 打印结果
    print("\n改进的分类器性能:")
    print(f"F1分数: {comparison['improved_f1']:.4f}")
    print(f"精确率: {comparison['improved_precision']:.4f}")
    print(f"召回率: {comparison['improved_recall']:.4f}")
    
    print("\n改进的分类器报告:")
    print(comparison['improved_report'])
    
    # 保存结果
    with open("improved_results.json", 'w') as f:
        json.dump({
            'improved_f1': comparison['improved_f1'],
            'improved_precision': comparison['improved_precision'],
            'improved_recall': comparison['improved_recall'],
            'improved_predictions': comparison['improved_predictions']
        }, f, indent=2)


if __name__ == "__main__":
    main()