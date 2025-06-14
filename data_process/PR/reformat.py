import json

# 读取文件内容
file_path = 'spider/pull_requests.txt'

with open(file_path, 'r', encoding='utf-8') as file:
    file_content = file.read()
    

# 修正格式：在字典之间插入逗号，并将内容包裹成 JSON 数组
fixed_content = file_content.replace("}\n{", "},\n{")

# 将内容包裹在方括号中，形成 JSON 数组
fixed_content = "[" + fixed_content + "]"

# 尝试将修正后的内容加载为 JSON
try:
    data = json.loads(fixed_content)
    print("数据加载成功：", data[0])
except json.JSONDecodeError as e:
    print(f"加载失败，错误信息：{e}")

# 重构 JSON 格式
restructured_data = {}
for item in data:
    project_name = item['项目名称']
    if project_name not in restructured_data:
        restructured_data[project_name] = {
            '项目star': item['项目star'],
            '项目prs': []
        }
    pr_info = {
        'pr网址': item['项目网址'],
        'pr的文本描述': item['pr的文本描述'],
        '变更的代码': item['变更的代码'],
        '最后的完整代码': item['最后的完整代码']
    }
    restructured_data[project_name]['项目prs'].append(pr_info)
    

# 将重构后的数据保存为 JSON 文件
with open('data/restructed_pull_request.json', 'w') as json_file:
    json.dump(restructured_data, json_file, indent=4, ensure_ascii=False)

print("Restructured JSON content saved to restructed_pull_request.json")