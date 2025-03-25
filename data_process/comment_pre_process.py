import json
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import string
import emoji
# nltk.download('punkt_tab')

def preprocess_punctuation(text):
    # 保存情感标点
    text = text.replace('!', ' EXCLAMATION_MARK ')
    text = text.replace('?', ' QUESTION_MARK ')
    text = text.replace('...', ' ELLIPSIS ')
    
    # 处理引号（在代码注释中经常使用）
    text = text.replace('"', ' QUOTE ').replace("'", ' QUOTE ')
    
    def replace_emoji(match):
        emoji_name = emoji.demojize(match.group(0))
        # 将形如:smile:的格式转换为EMOJI_SMILE
        emoji_token = 'EMOJI_' + emoji_name.replace(':', '').upper()
        return ' ' + emoji_token + ' '
    
    # 识别并替换所有Unicode表情符号
    emoji_pattern = emoji.get_emoji_regexp()
    text = emoji_pattern.sub(replace_emoji, text)

    # 去除其他标点符号
    punctuation_to_remove = string.punctuation.replace('!', '').replace('?', '')
    text = text.translate(str.maketrans('', '', punctuation_to_remove))
    
    return text

def preprocess_pr_comments(text):
    """
    对PR评论文本进行预处理
    
    参数:
        text (str): 输入的PR评论文本
    
    返回:
        tuple: (处理后的文本, 移除的代码块列表)
    """
    # 步骤1：识别并提取代码块
    code_pattern = r'```[\s\S]*?```|`[\s\S]*?`'
    code_blocks = re.findall(code_pattern, text)
    # 用占位符替换代码块
    text = re.sub(code_pattern, ' CODE_BLOCK ', text)
    
    # 步骤2：去除URL
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    text = re.sub(url_pattern, ' URL ', text)
    
    # 步骤3：去除HTML标签
    html_pattern = r'<.*?>'
    text = re.sub(html_pattern, '', text)
    
    # 步骤4：去除标点符号
    text = preprocess_punctuation(text)
    
    # 步骤5：转换为小写
    text = text.lower()
    
    # 步骤6：去除多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 步骤7：分词
    tokens = word_tokenize(text)
    
    # 步骤8：去除停用词（保留否定词）
    # stop_words = set(stopwords.words('english'))
    # negation_words = {'no', 'not', 'never', 'none', 'nobody', 'nowhere', 'neither', 'nor'}
    # filtered_stop_words = stop_words - negation_words
    # tokens = [word for word in tokens if word not in filtered_stop_words]
    
    # 步骤9：词干提取
    stemmer = PorterStemmer()
    stemmed_tokens = [stemmer.stem(word) for word in tokens]
    
    # 步骤10：重新组合为文本
    processed_text = ' '.join(stemmed_tokens)
    
    return processed_text

def main():
    with open('data/pr_full_comments.json', 'r') as f:
        total_comments = json.load(f)
    processed_total_comments = {}
    for project in total_comments:
        processed_project_comments = {}
        for pr_number in total_comments[project]:
            processed_comments = []
            for comment in total_comments[project][pr_number]:
                processed_comment = preprocess_pr_comments(comment)
                processed_comments.append(processed_comment)
            processed_project_comments[pr_number] = processed_comments
        processed_total_comments[project] = processed_project_comments

    with open('data/pre_processed_pr_full_comments.json', 'w') as f:
        json.dump(processed_total_comments)

if __name__ == "__main__":
    main()