import os
import json
import pandas as pd
from tqdm import tqdm
import tiktoken  # OpenAI's tokenizer

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

class TokenCalculator:
    """计算GitHub评论提示的token数量"""
    
    def __init__(self, model_name="gpt-4o-mini"):
        """
        初始化token计算器
        
        参数:
        model_name (str): 模型名称，用于选择适当的tokenizer
        """
        self.model_name = model_name
        self.categories = CATEGORIES
        self.prompt_template = self._create_prompt_template()
        
        # 根据模型选择合适的tokenizer
        if "cl100k" in model_name or "gpt-4" in model_name or "gpt-3.5" in model_name:
            self.encoding = tiktoken.get_encoding("cl100k_base")
        else:
            # 默认使用cl100k
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def _get_category_explanation(self, category):
        """获取类别的详细解释"""
        explanations = {
            1: "Share knowledge and experience with other people, or inform other people about new plans/updates.",
            2: "Attempt to obtain information or help from other people.",
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

            Pay special attention to comments indicating errors, bugs, or failures. These should generally be categorized as "problem discovery" (5).

            Here are some examples of categorization:

            {examples}

            Comment: 
            
            {{comment}}

            Return only the corresponding numeric label (1-7) without any additional explanation.

            categorization:
        """
        
        return template

    def count_tokens(self, comment):
        """
        计算单个评论提示的token数量
        
        参数:
        comment (str): GitHub评论
        
        返回:
        int: token数量
        """
        prompt = self.prompt_template.format(comment=comment)
        tokens = self.encoding.encode(prompt)
        return len(tokens)
    
    def batch_count_tokens(self, comments):
        """
        批量计算评论提示的token数量
        
        参数:
        comments (list): 评论列表
        
        返回:
        list: token数量列表
        """
        token_counts = []
        for comment in tqdm(comments, desc="计算token"):
            token_count = self.count_tokens(comment)
            token_counts.append(token_count)
        
        return token_counts

def main():
    """主函数"""
    # 初始化token计算器
    calculator = TokenCalculator(model_name="gpt-4o")
   
    # 统计token
    print("开始计算token...")

    # 加载数据
    with open('data/pre_processed_pr_full_comments_add_reviews.json', 'r') as f:
        pr_total_comments = json.load(f)
    
    # 存储token统计信息
    token_stats = {}
    all_tokens = []
    
    # 处理每个项目和PR
    for project_name in tqdm(pr_total_comments, desc="项目"):
        token_stats[project_name] = {}
        
        for pr_number in tqdm(pr_total_comments[project_name], desc=f"{project_name}的PR", leave=False):
            pr_comments = pr_total_comments[project_name][pr_number]
            
            # 计算每条评论的token
            token_counts = calculator.batch_count_tokens(pr_comments)
            all_tokens.extend(token_counts)
            
            # 计算统计信息
            token_stats[project_name][pr_number] = {
                "comment_count": len(pr_comments),
                "total_tokens": sum(token_counts),
                "avg_tokens": sum(token_counts) / len(token_counts) if token_counts else 0,
                "max_tokens": max(token_counts) if token_counts else 0,
                "min_tokens": min(token_counts) if token_counts else 0,
                "token_counts": token_counts
            }
    
    # 计算整体统计信息
    overall_stats = {
        "total_comments": len(all_tokens),
        "total_tokens": sum(all_tokens),
        "avg_tokens": sum(all_tokens) / len(all_tokens) if all_tokens else 0,
        "max_tokens": max(all_tokens) if all_tokens else 0,
        "min_tokens": min(all_tokens) if all_tokens else 0
    }
    
    # 保存结果
    with open('data/token_statistics.json', 'w') as f:
        json.dump({
            "overall": overall_stats,
            "projects": token_stats
        }, f, indent=2)
    
    # 打印整体统计信息
    print("\n===== Token 统计信息 =====")
    print(f"总评论数: {overall_stats['total_comments']}")
    print(f"总token数: {overall_stats['total_tokens']}")
    print(f"平均每条评论token数: {overall_stats['avg_tokens']:.2f}")
    print(f"最大token数: {overall_stats['max_tokens']}")
    print(f"最小token数: {overall_stats['min_tokens']}")


if __name__ == "__main__":
    main()