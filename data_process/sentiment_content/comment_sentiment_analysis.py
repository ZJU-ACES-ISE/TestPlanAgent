import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification, BertTokenizer, BertForSequenceClassification
import torch

# model_name = "tabularisai/multilingual-sentiment-analysis"
# model_name = "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis"
model_name = "model/bert"
tokenizer = BertTokenizer.from_pretrained("bert-base-cased", do_lower_case=True)
model = BertForSequenceClassification.from_pretrained(model_name, num_labels=3)
model.eval()

def predict_sentiment(texts):
    inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    sentiment_map = {0: "neutral", 1: "positive", 2: "negative"}
    return [sentiment_map[p] for p in torch.argmax(probabilities, dim=-1).tolist()]

with open('data/pre_processed_pr_full_comments.json', 'r') as f:
    pr_total_comments = json.load(f)

for project_name in pr_total_comments:
    for pr_number in pr_total_comments[project_name]:
        pr_comments = pr_total_comments[project_name][pr_number]
        pr_sentiments = predict_sentiment(pr_comments)
        pr_total_comments[project_name][pr_number] = {}
        if "negative" in pr_sentiments:
            pr_total_comments[project_name][pr_number]["PR_sentiment"] = "negative"
        else:
            pr_total_comments[project_name][pr_number]["PR_sentiment"] = "positive"
        pr_comments_and_sentiment = []
        for text, sentiment in zip(pr_comments, pr_sentiments):
            pr_comments_and_sentiment.append({"comment": text, "sentiment": sentiment})

        pr_total_comments[project_name][pr_number]["comments"] = pr_comments_and_sentiment
    print("1")
with open('data/pre_processed_contraction_pr_full_comments_sentiment_github_bert.json', 'w') as f:
    json.dump(pr_total_comments, f)

