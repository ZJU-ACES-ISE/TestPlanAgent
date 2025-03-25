from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

model_name = "tabularisai/multilingual-sentiment-analysis"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

def predict_sentiment(texts):
    inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=512)
    with torch.no_grad():
        outputs = model(**inputs)
    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    sentiment_map = {0: "Very Negative", 1: "Negative", 2: "Neutral", 3: "Positive", 4: "Very Positive"}
    return [sentiment_map[p] for p in torch.argmax(probabilities, dim=-1).tolist()]

texts = [
    "@koji thanks i think this is a bug. i guess youre running into this issue because the labware is incompatible with the pipette (since you are using an 8-channel with a tuberack). I guess we need to disable the well selection if that error comes up. I'll log the bug!",
    "@shlokamin can i pick your brain about this? so there are 3 new fields introduced with this pr: pickUpTip_location, pickUpTip_wellNames, dropTip_wellNames. Each of them are optional for the user to add so we can create the blank form with each of these values as undefined. That means that we don't break the import/export (which if we did, then we'd need a new migration and im unsure how we can put all of that behind a ff). But that does not follow the current pattern. All the other fields default to null or an empty array, etc. Is there harm in defaulting to undefined?",
    "the changes look good to me. the sandbox worked as expected. there is one e2e test error on transferSettings.cy.js"
]
texts_pre_precess = [
    'koji thank think bug guess your run issu labwar incompat pipett sinc use 8channel tuberack guess need disabl well select error come ill log bug', 'shlokamin pick brain 3 new field introduc pr pickuptiploc pickuptipwellnam droptipwellnam option user add creat blank form valu undefin mean dont break importexport wed need new migrat im unsur put behind ff not follow current pattern field default null empti array etc harm default undefin', 'chang look good sandbox work expect one e2e test error transfersettingscyj'
]
for text, sentiment in zip(texts_pre_precess, predict_sentiment(texts_pre_precess)):
    print(f"Text: {text}\nSentiment: {sentiment}\n")
