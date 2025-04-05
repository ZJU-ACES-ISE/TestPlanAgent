import json
from llm_process_3 import llm_restructure_pr_body
from tqdm import tqdm

def save_data(data, filename='data/llm_restructed_pull_request.json'):
    with open(filename, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4, ensure_ascii=False)

def main():
    dataset_dir = "data/restructed_pull_request.json"
    
    # 读取数据
    with open(dataset_dir, "r", encoding='utf-8') as f:
        data = json.load(f)
    
    step = 500  # 定义步长
    processed_prs = 0  # 计数已处理的 PR 数量
    
    # 遍历每个项目
    for project_name, project_info in data.items():
        has_test_plan_num = 0
        prs = project_info.get('项目prs', [])
        
        # 使用 tqdm 显示项目内 PR 处理进度
        for pr_info in tqdm(prs, desc=f"Processing PRs in project {project_name}"):
            try:
                # 调用 API 进行 PR 重构
                llm_pr_body = llm_restructure_pr_body(pr_info['pr的文本描述'])
                
                # 清理返回的字符串并解析为 JSON
                restructured_pr_body = llm_pr_body.strip('```json').strip('```')
                json_content = json.loads(restructured_pr_body)
                
                # 更新测试计划信息
                if json_content.get("Test plan", "None") != "None":
                    pr_info["测试计划"] = json_content["Test plan"]
                    has_test_plan_num += 1
                else:
                    pr_info["测试计划"] = "None"
            except Exception as e:
                print(f"Error processing PR: {e}")
                pr_info["测试计划"] = "Error"
            
            processed_prs += 1
            
            # 每达到一个步长，保存一次数据
            if processed_prs % step == 0:
                print(f"已处理 {processed_prs} 个 PR，开始保存中间结果...")
                save_data(data)
                print("保存完成。")
        
        # 更新项目的测试计划 PR 数量
        project_info["存在测试计划的PR数量"] = has_test_plan_num
        print(f"项目 {project_name} 中共有： {len(prs)} PR，存在测试计划的PR数量： {has_test_plan_num}")
    
    # 最终保存所有数据
    print("所有项目处理完毕，开始保存最终结果...")
    save_data(data)
    print("最终结果已保存。")

if __name__ == "__main__":
    main()
