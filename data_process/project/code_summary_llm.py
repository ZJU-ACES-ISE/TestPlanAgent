def llm(system_prompt, user_prompt, model):
    """
    用给定的提示调用语言模型API。
    
    Args:
        system_prompt (str): 系统提示为LLM
        user_prompt (str, optional): 用户提示llm
        model (str): 模型名称
        
    Returns:
        str: LLM响应内容
    """
    if 'deepseek' in model:
        api_key = "sk-da7a5e373876461f9efb80e7c15828a5"
        url = "https://api.deepseek.com/chat/completions"
        
    elif 'qwen' in model:
        api_key = "sk-6072ffbc181542f2862a1fd04d8291c0"
        url = "http://localhost:8000/v1/chat/completions"
    else:
        api_key = "sk-vhd396de43bb46de996a85f47f3be8579fe14ce8d49ZYSk3"
        if 'claude' in model:
            url = "https://api.gptsapi.net/v1/messages"
        else:
            url = "https://api.gptsapi.net/v1/chat/completions"

    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    if 'claude' in model:
        data = {
            "model": model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }
    else:    
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        }
    
    max_retries = 5
    response = None
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Request failed. Retrying... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(2 ** attempt)
                continue
            else:
                print(e)
                raise e
    
    if response is None:
        raise Exception("All retry attempts failed")
    
    response_dict = json.loads(response.text.strip())
    if 'claude' in model:
        content = response_dict["content"][0]["text"]
    else:    
        content = response_dict['choices'][0]['message']['content']
    return content

def summary():
    # 定义10个英文问题

    model = "qwen-coder-14B"  # 设置默认模型
    system_prompt = """
    You are an expert code summarization assistant specialized in creating concise and informative descriptions of classes and functions. Your task is to analyze code snippets and generate clear, accurate summaries that explain:

    1. The purpose and functionality of the class or function
    2. Key parameters and return values
    3. Important behaviors, algorithms, or patterns used
    4. Potential side effects or notable constraints
    5. The role of the code within the larger system (when context is available)

    Follow these guidelines:
    - Be concise and precise - aim for 1-3 sentences for functions and 2-5 sentences for classes
    - Use technical terminology appropriately but remain understandable 
    - Focus on the "what" and "why", not just the "how"
    - Avoid obvious restatements of function/class names
    - Prioritize information that would be most useful to a developer trying to understand the code
    - Maintain a consistent style that could be used in documentation
    - For classes, summarize both the overall purpose and notable methods
    - For functions, emphasize inputs, outputs, and key transformations

    Your summaries should be informative enough to help developers understand the code's purpose without needing to read the implementation details.
    """
    user_promt = """
    Please provide a concise summary for the following [class/function]. Focus on its purpose, key behaviors, and role within the system. Make sure to highlight important parameters, return values, and any notable side effects or constraints.

    ```python
    function Table(props: TableProps) {\n  const { headerData, rowData, columnWidths } = props;\n\n  const autoColumnWidths = Array(headerData.length).fill(1);\n  const notEmptyColumnWidths = columnWidths ?? autoColumnWidths;\n  const sumColumnWidths = notEmptyColumnWidths.reduce((acc, i) => acc + i, 0);\n  const customStyles = props.customStyles\n    ? props.customStyles\n    : EMPTY_CUSTOM_STYLES;\n  const thisTableStyle = {\n    ...tableStyle,\n    ...customStyles.tableStyle,\n  };\n  const thisHeaderStyle = {\n    ...headerStyle,\n    ...customStyles.headerStyle,\n  };\n  const thisThStyle = {\n    ...thStyle,\n    ...customStyles.thStyle,\n  };\n  const thisTdStyle = {\n    ...tdStyle,\n    ...customStyles.tdStyle,\n  };\n\n  return (\n    <table style={thisTableStyle}>\n      <thead style={thisHeaderStyle}>\n        <tr>\n          {headerData.map((col, idx) => (\n            <th\n              key={idx}\n              style={{\n                ...thisThStyle,\n                width: `${\n                  (notEmptyColumnWidths[idx] * 100) / sumColumnWidths\n                }%`,\n              }}\n            >\n              {col}\n            </th>\n          ))}\n        </tr>\n      </thead>\n      <tbody>\n        {rowData.map((row, rowIdx) => (\n          <tr key={rowIdx}>\n            {row.map((col, colIdx) => (\n              <td key={colIdx} style={thisTdStyle}>\n                {col}\n              </td>\n            ))}\n          </tr>\n        ))}\n      </tbody>\n    </table>\n  );\n}
    ```
    """
    try:
        # 请求LLM回答
        result = llm(system_prompt, user_promt, model)
        
        print(f"\nAnswer:")
        print(result)
        
        # 添加间隔时间，避免频繁请求
        time.sleep(2)
        
    except Exception as e:
        print(f"Error occurred: {e}")
        time.sleep(5)  # 出错时等待更长时间再重试