import json
import re
from nltk.tokenize import word_tokenize
import string
import emoji
import nltk
from nltk.tokenize import word_tokenize

def expand_contractions(text, contractions_dict):

    # 生成正则表达式模式，匹配字典中的所有键
    contractions_pattern = re.compile('({})'.format('|'.join(contractions_dict.keys())), 
                                      flags=re.IGNORECASE|re.DOTALL)
    
    def expand_match(contraction):
        match = contraction.group(0)
        first_char = match[0]
        expanded = contractions_dict.get(match.lower(), match)
        expanded = first_char + expanded[1:]
        return expanded
        
    # 使用替换函数对文本中匹配的缩写进行展开
    expanded_text = contractions_pattern.sub(expand_match, text)
    return expanded_text

def replace_emoji(match):
    emoji_name = emoji.demojize(match.group(0))
    # 将形如:smile:的格式转换为EMOJI_SMILE
    emoji_token = 'EMOJI_' + emoji_name.replace(':', '').upper()
    return ' ' + emoji_token + ' '

def preprocess_punctuation(text):
    # 保存情感标点
    text = text.replace('!', ' EXCLAMATION_MARK ')
    text = text.replace('?', ' QUESTION_MARK ')
    text = text.replace('...', ' ELLIPSIS ')
    
    with open('data_process/contractions_dict.json', 'r') as f:
        contractions_dict = json.load(f)
    
    text = expand_contractions(text, contractions_dict)
    
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
    # 识别并提取代码块
    code_pattern = r'```[\s\S]*?```|`[\s\S]*?`'

    # 用占位符替换代码块
    text = re.sub(code_pattern, ' CODEBLOCK ', text)
    
    # 去除URL
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    text = re.sub(url_pattern, ' ', text)
    
    # 去除HTML标签
    html_pattern = r'<.*?>'
    text = re.sub(html_pattern, '', text)
    
    # 转换为小写
    text = text.lower()

    # 去除标点符号
    # text = preprocess_punctuation(text)
    
    # 去除多余空格
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 分词
    # tokens = word_tokenize(text)
    
    # processed_text = ' '.join(tokens)
    
    return text

def main():
    with open('data/pr_full_comments_add_reviews.json', 'r') as f:
        total_comments = json.load(f)
    processed_total_comments = {}
    for project in total_comments:
        processed_project_comments = {}
        for pr_number in total_comments[project]:
            processed_comments = []
            for comment in total_comments[project][pr_number]:
                processed_comment = preprocess_pr_comments(comment)
                if len(processed_comment.split(' ')) > 2:
                    processed_comments.append(processed_comment)
            processed_project_comments[pr_number] = processed_comments
        processed_total_comments[project] = processed_project_comments

    with open('data/pre_processed_pr_full_comments_add_reviews.json', 'w') as f:
        json.dump(processed_total_comments, f)

if __name__ == "__main__":
    main()