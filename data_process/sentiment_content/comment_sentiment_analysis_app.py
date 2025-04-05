import json
from transformers import AutoTokenizer, AutoModelForSequenceClassification, BertTokenizer, BertForSequenceClassification
import torch
from flask import Flask, request, jsonify

# Initialize Flask app
app = Flask(__name__)

# Load model and tokenizer
# model_name = "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis"
# model_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
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

@app.route('/predict', methods=['POST'])
def predict():
    # Get data from request
    data = request.json
    
    if not data or 'texts' not in data:
        return jsonify({"error": "Please provide texts in the request body"}), 400
    
    texts = data['texts']
    
    # Make prediction
    sentiments = predict_sentiment(texts)
    
    # Prepare response
    response = []
    for text, sentiment in zip(texts, sentiments):
        response.append({
            "text": text,
            "sentiment": sentiment
        })
    
    return jsonify(response)

@app.route('/', methods=['GET'])
def home():
    return """
    <h1>Sentiment Analysis API</h1>
    <p>Send a POST request to /predict with a JSON body containing a list of texts:</p>
    <pre>
    {
        "texts": ["This is a positive text", "This is a negative text"]
    }
    </pre>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)