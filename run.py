import os
import argparse
import tqdm
import yaml
import json
import sys
import traceback
import logging
import concurrent.futures
from pathlib import Path
from urllib.parse import urlparse
from tasks.task_factory import TaskFactory
sys.path.append(str(Path(__file__).resolve().parents[1]))  # 将父级目录加入执行目录列表

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("error_log.txt"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_runner")

def generate_config(pr_url, llm_model, output_dir, strategy, judge_llm_model, summary_llm_molde, api_key=None, llm_url=None):
    """
    Generate configuration for a test plan task.
    
    Args:
        pr_url (str): GitHub PR URL
        llm_model (str): LLM model to use
        output_dir (str): Output directory for test plans
        strategy (str): Test plan generation strategy
        api_key (str, optional): API key for LLM
        llm_url (str, optional): API URL for LLM
        
    Returns:
        dict: Configuration dictionary
    """
    parsed_url = urlparse(pr_url)
    path_parts = parsed_url.path.strip('/').split('/')
    
    if len(path_parts) < 4 or path_parts[-2] != 'pulls':
        raise ValueError("Invalid PR URL format. Expected format: https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}")
    
    org = path_parts[1]
    repo = path_parts[2]
    pr_number = path_parts[4]
    
    diff_url = f"https://api.github.com/repos/{org}/{repo}/pulls/{pr_number}/files"
    
    output_file_name = f"{llm_model}_{pr_number}.json"


    
    # Create configuration
    config = {
        'CKG': {
            'project_dir': f"./test_project/{repo}",
            'graph_pkl_dir': f"./CKG/{repo}_graph.pkl"
        },
        'Agent': {
            'diff_url': diff_url,
            'PR_url': pr_url,
            'llm_model': llm_model,
            # 'api_key': api_key,
            # 'llm_url': llm_url,
            'output_dir': f'{os.path.join(output_dir, strategy, repo, "Test-Plan")}',
            'output_file_name': output_file_name,
            'strategy': strategy
        },
        'Judge': {
            'llm_model': judge_llm_model, 
            'tmp_dir': f'{os.path.join(output_dir, strategy, repo, "PR-Content")}',
            'pull_number': pr_number,
            'repo': repo,
            'scores_output_dir': f'{os.path.join(output_dir, strategy, repo, "scores")}'
        },
        'Embedding':{
            'load_embedding': os.path.join(output_dir, strategy, repo, "embedding.json"),
            'info_file': os.path.join(output_dir, strategy, repo, "info_file.json")
        },
        'Summary':{
            'code_summary_file_path': os.path.join(output_dir, "code_summary.json"),
            'llm_model': summary_llm_molde
        },
        'output_dir': output_dir,
        
    }
    
    return config

def save_config(config, output_file='./source/config.yaml'):
    """
    将配置保存到YAML文件。
    
    Args:
        config (dict): 配置字典
        output_file (str, optional): 输出文件路径
        
    Returns:
        str: 保存配置文件的路径
    """
    # 确保存在目录
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    print(f"Configuration saved to {output_file}")
    return output_file


def save_result(result, output_file):
    with open(output_file, 'w') as f:
        json.dump(result, f)

def process_single_pr(config, skip_generation=False, test_plan_path=None, score=True):
    """
    处理单个PR的测试计划生成和评分。
    
    Args:
        config (dict): 配置字典
        skip_generation (bool): 是否跳过测试计划生成
        test_plan_path (str): 现有测试计划的路径
        score (bool): 是否对测试计划进行评分
        
    Returns:
        tuple: (test_plan, scores)
    """
    test_plan = None
    scores = None
    
    # 生成测试计划，如果不跳过
    if not skip_generation:
        try:
            # 创建和运行任务
            task = TaskFactory.create_task(config, "generator")
            test_plan = task.run()
            print(f"Test plan generation completed successfully for PR: {config['Agent']['PR_url']}!")
            
            # 保存测试计划路径
            if test_plan != None:
                test_plan_path = os.path.join(
                    config['Agent']['output_dir'],
                    config['Agent']['output_file_name']
                )
        except Exception as e:
            print(f"Error generating test plan for PR {config['Agent']['PR_url']}: {e}")
            error_msg = traceback.format_exc()
            logger.error(f"Unexpected error: {e}")
            logger.error(f"Error details:\n{error_msg}")
            if not test_plan:
                # 没有测试计划就无法得分
                return None, None
    else:
        # 使用提供的测试计划路径
        print(f"Skipping test plan generation, using: {test_plan_path}")

    test_plan_path = os.path.join(
        config['Agent']['output_dir'],
        config['Agent']['output_file_name']
    )
    # 如果要求得分测试计划
    if score and test_plan_path:
        try:
            # 创建和运行法官任务
            judge_task = TaskFactory.create_task(config, "judge", test_plan_path)
            scores = judge_task.run()
            print(f"Test plan scoring completed successfully for PR: {config['Agent']['PR_url']}!")
            
            # 打印分数摘要
            print(f"\nTest Plan Scores for PR {config['Agent']['PR_url']}:")
            for criterion, details in scores['evaluation'].items():
                if isinstance(details, dict):
                    print(f"- {criterion.capitalize()}: {details['score']}/10")
                else:
                    print(f"- {criterion.capitalize()}: {details}")
            
        except Exception as e:
            print(f"Error scoring test plan for PR {config['Agent']['PR_url']}: {e}")
            error_msg = traceback.format_exc()
            logger.error(f"Unexpected error: {e}")
            logger.error(f"Error details:\n{error_msg}")
    
    return test_plan, scores

def read_pr_urls_from_file(file_path):
    """
    从文件中读取PR URL列表。
    
    Args:
        file_path (str): 文件路径
        
    Returns:
        list: PR URL列表
    """
    with open(file_path, 'r') as f:
        # 移除每行末尾的空白字符，并过滤掉空行
        urls = [line.strip() for line in f.readlines() if line.strip()]
    return urls

def run(args):
    """
    运行测试计划生成和评分任务。
    
    Args:
        args: 命令行参数
        
    Returns:
        dict: 每个PR的结果
    """
    # 检查PR URL是否是文件路径
    pr_urls = []
    if os.path.isfile(args.pr_url):
        # 从文件读取PR URL列表
        pr_urls = read_pr_urls_from_file(args.pr_url)
        print(f"Read {len(pr_urls)} PR URLs from file: {args.pr_url}")
    else:
        # 单个PR URL
        pr_urls = [args.pr_url]
    
    results = {}
    
    if args.multi_threading and len(pr_urls) > 1:
        # 使用线程池并发处理多个PR
        print(f"Processing {len(pr_urls)} PRs in parallel with {args.max_workers} workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # 为每个PR创建配置
            configs = []
            for pr_url in pr_urls:
                config = generate_config(
                    pr_url, 
                    args.model, 
                    args.output_dir, 
                    args.strategy,
                    args.judge_model,
                    args.summary_model,
                    args.api_key,
                    args.llm_api,
                )
                
                # 如果要求保存配置
                if args.save_config:
                    # 为每个PR创建单独的配置文件
                    parsed_url = urlparse(pr_url)
                    path_parts = parsed_url.path.strip('/').split('/')
                    pr_number = path_parts[4]
                    config_file = os.path.join(os.path.dirname(args.config_output_dir), f"config_{pr_number}.yaml")
                    save_config(config, config_file)
                
                configs.append(config)
            
            # 提交所有任务到线程池
            future_to_config = {
                executor.submit(
                    process_single_pr, 
                    config, 
                    args.skip_generation, 
                    args.test_plan_path, 
                    args.score
                ): config for config in configs
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_config):
                config = future_to_config[future]
                pr_url = config['Agent']['PR_url']
                try:
                    test_plan, scores = future.result()
                    results[pr_url] = {
                        'test_plan': test_plan,
                        'scores': scores
                    }
                except Exception as e:
                    print(f"Processing PR {pr_url} generated an exception: {e}")
                    results[pr_url] = {
                        'error': str(e)
                    }
    else:
        # 顺序处理PR
        for pr_url in tqdm.tqdm(pr_urls, desc="Processing PRs"):
            config = generate_config(
                pr_url, 
                args.model, 
                args.output_dir, 
                args.strategy,
                args.judge_model,
                args.summary_model,
                args.api_key,
                args.llm_api
            )
            
            # 如果要求保存配置
            if args.save_config:
                # 为每个PR创建单独的配置文件
                parsed_url = urlparse(pr_url)
                path_parts = parsed_url.path.strip('/').split('/')
                pr_number = path_parts[4]
                config_file = os.path.join(os.path.dirname(args.config_output_dir), f"config_{pr_number}.yaml")
                save_config(config, config_file)
            
            test_plan, scores = process_single_pr(
                config, 
                args.skip_generation, 
                args.test_plan_path, 
                args.score
            )
            
            results[pr_url] = {
                'test_plan': test_plan,
                'scores': scores
            }
    results_path = os.path.join(config['output_dir'], config['Agent']['strategy'], f"{config['Agent']['llm_model']}_{config['Judge']['llm_model']}_result.json")
    save_result(results, results_path)
    return results

def main(): 
    """
    解析参数并运行任务的主要功能。  
    """
    parser = argparse.ArgumentParser(description='Generate and score test plans for GitHub PRs')

    # PR和模型设置
    parser.add_argument('--pr_url', default='/data/veteran/project/TestPlanAgent/data/PR/PR_URL_for_test_resume.txt', 
                       help='GitHub PR URL or file containing PR URLs')
    parser.add_argument('--model', type=str, 
                       choices=['claude-3-7-sonnet-20250219', 'deepseek-chat', 'qwen-max-latest',
                               'gpt-3.5-turbo', 'qwen2.5-coder-32b-instruct', 
                               'qwen2.5-coder-14b-instruct'], 
                       default='gpt-4o',
                       help='LLM model to use')
    
    # API设置
    parser.add_argument('--api-key', default='', help='LLM API key')
    parser.add_argument('--llm-api', default='', help='LLM API URL')
    
    # 输出设置
    parser.add_argument('--config-output-dir', default='./source/config.yaml', 
                       help='Output YAML file')
    parser.add_argument('--output-dir', default='./result', 
                       help='Test plan output directory')
    parser.add_argument('--save-config', action='store_true',
                       help='Save configuration to file')
    
    # 任务设置
    parser.add_argument('--strategy', type=str,
                       choices=['InOut', 'Embedding', 'ReAct', 'TOT'], 
                       default='InOut',
                       help='Test plan generation strategy')
    
    # 裁判设置
    parser.add_argument('--score', default=True, type=bool,
                       help='Score the generated test plan')
    parser.add_argument('--skip-generation', default=False,
                       help='Skip test plan generation, only score an existing test plan')
    parser.add_argument('--test-plan-path', default="", type=str,
                       help='Path to existing test plan to score (required if --skip-generation is used)')
    parser.add_argument('--judge-model', type=str,
                        default='claude-3-7-sonnet-20250219',
                        help='Judge LLM model to use')
    
    # 摘要设置
    parser.add_argument('--summary-model', type=str,
                        default='gpt-4o',
                        help='Judge LLM model to use')
    
    # 多线程参数
    parser.add_argument('--multi-threading', default=False,
                       help='Enable multi-threading for processing multiple PRs')
    parser.add_argument('--max-workers', type=int, default=5,
                       help='Maximum number of worker threads when multi-threading is enabled')
    
    args = parser.parse_args()
    
    # 验证论点
    # if args.skip_generation and not args.test_plan_path:
    #     print("Error: --test-plan-path is required when using --skip-generation")
    #     return 1
    
    # try:
    results = run(args)
    print(f"Processed {len(results)} PRs")
    # except Exception as e:
    #     print(f"Failed to run: {e}")
    #     error_msg = traceback.format_exc()
    #     logger.error(f"Unexpected error: {e}")
    #     logger.error(f"Error details:\n{error_msg}")
    #     return 1
    
    return 0

if __name__ == "__main__":
    main()