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


class LLMClassifier:
    """使用LLM进行GitHub评论分类的类"""
    
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
        
    def _create_prompt_template(self):
        """创建分类提示模板"""
        category_descriptions = "\n".join([f"{k}: {v}" for k, v in self.categories.items()])
        
        template = f"""
            You are a professional code review comment classifier. Please analyze the following GitHub code review comment and classify it into one of these 13 categories:

            {category_descriptions}

            Return only the corresponding numeric label (1-13) without any additional explanation.

            GitHub code review comment:
            {{comment}}

            Classification result:
        """
        
        return template
    
    def classify_comment(self, comment):
        """
        使用LLM对单个评论进行分类
        
        参数:
        comment (str): 需要分类的GitHub评论
        
        返回:
        int: 分类标签(1-13)
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
    
    def batch_classify(self, comments, batch_size=10, sleep_time=0.1):
        """
        批量分类评论
        
        参数:
        comments (list): 评论列表
        batch_size (int): 批处理大小，防止API限制
        sleep_time (int): 批次间休眠时间（秒）
        
        返回:
        list: 分类结果列表
        """
        results = []
        
        for i in tqdm(range(0, len(comments), batch_size)):
            batch = comments[i:i+batch_size]
            batch_results = []
            
            for comment in batch:
                classification = self.classify_comment(comment)
                batch_results.append(classification)
                # time.sleep(0.1)  # 短暂休眠，防止请求过快
            
            results.extend(batch_results)
            
            # if i + batch_size < len(comments):
                # time.sleep(sleep_time)  # 批次间休眠
                
        return results


def load_data(comments_file, labels_file):
    """
    加载评论和标签数据
    
    参数:
    comments_file (str): 评论文件路径
    labels_file (str): 标签文件路径
    
    返回:
    tuple: (评论列表, 标签列表)
    """
    with open(comments_file, 'r', encoding='utf-8') as f:
        comments = [line.strip() for line in f.readlines()]
    comments = comments[:100]
    with open(labels_file, 'r', encoding='utf-8') as f:
        labels = [int(line.strip()) for line in f.readlines()]
    labels = labels[:100]
    # 确保数据长度一致
    assert len(comments) == len(labels), "评论和标签数量不匹配"
    
    return comments, labels


def evaluate_performance(y_true, y_pred):
    """
    评估分类性能
    
    参数:
    y_true (list): 真实标签
    y_pred (list): 预测标签
    
    返回:
    dict: 性能指标字典
    """
    # 计算总体性能
    accuracy = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    
    # 计算每个类别的精确率、召回率和F1分数
    precision_macro = precision_score(y_true, y_pred, average='macro')
    recall_macro = recall_score(y_true, y_pred, average='macro')
    f1_macro = f1_score(y_true, y_pred, average='macro')
    
    # 计算加权平均
    precision_weighted = precision_score(y_true, y_pred, average='weighted')
    recall_weighted = recall_score(y_true, y_pred, average='weighted')
    f1_weighted = f1_score(y_true, y_pred, average='weighted')
    
    # 生成分类报告
    report = classification_report(y_true, y_pred, target_names=[CATEGORIES[i] for i in sorted(CATEGORIES.keys())])
    
    # 混淆矩阵
    cm = confusion_matrix(y_true, y_pred, labels=list(range(1, 14)))
    
    return {
        'accuracy': accuracy,
        'precision_macro': precision_macro,
        'recall_macro': recall_macro,
        'f1_macro': f1_macro,
        'precision_weighted': precision_weighted,
        'recall_weighted': recall_weighted,
        'f1_weighted': f1_weighted,
        'report': report,
        'confusion_matrix': cm
    }


def plot_confusion_matrix(cm, categories):
    """
    绘制混淆矩阵热图
    
    参数:
    cm (numpy.ndarray): 混淆矩阵
    categories (dict): 类别映射
    """
    plt.figure(figsize=(10, 8))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=[f"{i}" for i in range(1, 14)],
                yticklabels=[f"{i}" for i in range(1, 14)])
    plt.xlabel('预测标签')
    plt.ylabel('真实标签')
    plt.title('混淆矩阵')
    plt.tight_layout()
    plt.savefig('confusion_matrix.png')
    plt.close()


def analyze_errors(comments, true_labels, pred_labels):
    """
    分析错误分类的评论
    
    参数:
    comments (list): 评论列表
    true_labels (list): 真实标签
    pred_labels (list): 预测标签
    
    返回:
    list: 错误分类的评论及其标签
    """
    errors = []
    
    for comment, true_label, pred_label in zip(comments, true_labels, pred_labels):
        if true_label != pred_label:
            errors.append({
                'comment': comment,
                'true_label': true_label,
                'true_category': CATEGORIES[true_label],
                'pred_label': pred_label,
                'pred_category': CATEGORIES[pred_label]
            })
    
    return errors


def save_results(predictions, metrics, errors, output_dir='results'):
    """
    保存实验结果
    
    参数:
    predictions (list): 预测结果
    metrics (dict): 性能指标
    errors (list): 错误分析
    output_dir (str): 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存预测结果
    with open(f"{output_dir}/predictions.json", 'w') as f:
        json.dump(predictions, f, indent=2)
    
    # 保存性能指标
    metrics_to_save = {k: v for k, v in metrics.items() if k not in ['report', 'confusion_matrix']}
    
    with open(f"{output_dir}/metrics.json", 'w') as f:
        json.dump(metrics_to_save, f, indent=2)
    
    # 保存分类报告
    with open(f"{output_dir}/classification_report.txt", 'w') as f:
        f.write(metrics['report'])
    
    # 保存错误分析
    with open(f"{output_dir}/error_analysis.json", 'w') as f:
        json.dump(errors, f, indent=2)


def main():
    """主函数"""
    # 设置API密钥
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("请设置OPENAI_API_KEY环境变量")
    
    # 初始化分类器
    classifier = LLMClassifier(api_key=api_key)
    
    # 加载数据
    comments_file = "data/review_comments.txt"
    labels_file = "data/review_comments_labels.txt"
    comments, true_labels = load_data(comments_file, labels_file)
    
    # 打印数据集信息
    print(f"加载了 {len(comments)} 条评论和对应标签")
    
    # 分类评论
    print("开始分类...")
    pred_labels = classifier.batch_classify(comments)
    
    # 过滤掉API调用失败的结果
    valid_indices = [i for i, pred in enumerate(pred_labels) if pred is not None]
    filtered_comments = [comments[i] for i in valid_indices]
    filtered_true_labels = [true_labels[i] for i in valid_indices]
    filtered_pred_labels = [pred_labels[i] for i in valid_indices]
    
    print(f"成功分类了 {len(filtered_comments)} 条评论，失败了 {len(comments) - len(filtered_comments)} 条")
    
    # 评估性能
    performance = evaluate_performance(filtered_true_labels, filtered_pred_labels)
    
    # 打印性能指标
    print("\n性能指标:")
    print(f"准确率: {performance['accuracy']:.4f}")
    print(f"宏平均精确率: {performance['precision_macro']:.4f}")
    print(f"宏平均召回率: {performance['recall_macro']:.4f}")
    print(f"宏平均F1分数: {performance['f1_macro']:.4f}")
    print(f"加权平均精确率: {performance['precision_weighted']:.4f}")
    print(f"加权平均召回率: {performance['recall_weighted']:.4f}")
    print(f"加权平均F1分数: {performance['f1_weighted']:.4f}")
    
    print("\n分类报告:")
    print(performance['report'])
    
    # 绘制混淆矩阵
    plot_confusion_matrix(performance['confusion_matrix'], CATEGORIES)
    
    # 错误分析
    errors = analyze_errors(filtered_comments, filtered_true_labels, filtered_pred_labels)
    print(f"错误分类数量: {len(errors)}")
    
    # 保存结果
    save_results(
        [{'comment': c, 'true_label': t, 'pred_label': p} 
         for c, t, p in zip(filtered_comments, filtered_true_labels, filtered_pred_labels)],
        performance,
        errors
    )
    
    print("实验完成.结果已保存到results目录")


if __name__ == "__main__":
    main()