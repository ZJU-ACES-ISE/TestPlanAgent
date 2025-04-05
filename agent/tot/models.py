import os
import openai
import backoff
import requests 

completion_tokens = prompt_tokens = 0

api_key = os.getenv("OPENAI_API_KEY", "")
# api_key = "sk-Y9Ba7ca3cb6235a6b6f2d371c3bc11db13f0a1e8bf9a4p5o"
if api_key != "":
    openai.api_key = api_key
else:
    print("Warning: OPENAI_API_KEY is not set")
    
api_base = os.getenv("OPENAI_API_BASE", "https://api.gptsapi.net/v1/chat/completions")
if api_base != "":
    print("Warning: OPENAI_API_BASE is set to {}".format(api_base))
    openai.api_base = api_base

# 使用 backoff 进行重试的请求函数
@backoff.on_exception(backoff.expo, requests.exceptions.RequestException)
def completions_with_backoff(**kwargs):

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {kwargs.pop('api_key', None)}"
    }
    data = kwargs
    response = requests.post(api_base, headers=headers, json=data)
    response.raise_for_status()  # 如果响应状态码不是 200，会抛出异常
    return response.json()

def gpt(prompt, model="gpt-4", temperature=0.7, max_tokens=1000, n=1, stop=None) -> list:
    messages = [{"role": "user", "content": prompt}]
    return chatgpt(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n, stop=stop)
    
def chatgpt(messages, model="gpt-4", temperature=0.7, max_tokens=1000, n=1, stop=None) -> list:
    global completion_tokens, prompt_tokens
    outputs = []
    while n > 0:
        cnt = min(n, 20)
        n -= cnt
        
        # 准备请求参数
        params = {
            "model": model, 
            "messages": messages, 
            "temperature": temperature, 
            "max_tokens": max_tokens, 
            "n": cnt
        }
        
        if stop:
            params["stop"] = stop
            
        if api_key:
            params["api_key"] = api_key
            
        # 发送请求
        res = completions_with_backoff(**params)
        
        # 处理响应
        outputs.extend([choice["message"]["content"] for choice in res["choices"]])
        
        # 记录 token 使用情况
        completion_tokens += res["usage"]["completion_tokens"]
        prompt_tokens += res["usage"]["prompt_tokens"]
        
    return outputs
    
def gpt_usage(backend="gpt-4"):
    global completion_tokens, prompt_tokens
    if backend == "gpt-4":
        cost = completion_tokens / 1000 * 0.06 + prompt_tokens / 1000 * 0.03
    elif backend == "gpt-3.5-turbo":
        cost = completion_tokens / 1000 * 0.002 + prompt_tokens / 1000 * 0.0015
    elif backend == "gpt-4o":
        cost = completion_tokens / 1000 * 0.00250 + prompt_tokens / 1000 * 0.01
    return {"completion_tokens": completion_tokens, "prompt_tokens": prompt_tokens, "cost": cost}
