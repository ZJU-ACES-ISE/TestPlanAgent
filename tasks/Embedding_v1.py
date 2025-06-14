import os
import json
from pathlib import Path
import torch
import numpy as np
from transformers import T5EncoderModel, RobertaTokenizer
from tqdm import tqdm
from tree_sitter_languages import get_parser
from tasks.BaseTask import BaseTask
from prompt.embedding.test_plan import EMBEDDING_TEST_PLAN_SYSTEM_PROMPT, EMBEDDING_TEST_PLAN_USER_PROMPT

class Embedding(BaseTask):
    """
    实施测试计划生成的嵌入策略。
    扩展底座类。
    """
    
    def __init__(self, config):
        """
        用提供的配置初始化嵌入任务。
        
        Args:
            config (dict): 任务的配置字典
        """
        super().__init__(config)
        self.model_name = "Salesforce/codet5p-110m-embedding"
        self.device = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")
        self.tokenizer = None
        self.model = None
        self.code_embeddings = None
        self.code_info = []
        self.repo_code_structure = None
        self.analyze_code_files(self.config['CKG']['project_dir'])
        self.save_results_to_json(self.repo_code_structure, os.path.join(self.config['CKG']['project_dir'], "code_structure.json"))
    
    def analyze_code_files(self, directory):
        # 初始化不同类型文件的解析器
        parsers = {
            'tsx': get_parser('tsx'),
            'ts': get_parser('typescript'),
            'py': get_parser('python'),
            'js': get_parser('javascript')
        }
        
        # 结果将按照文件树结构存储
        results = {}
        
        # 遍历目录中的所有文件
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                ext = file.split('.')[-1]
                
                if ext not in parsers:
                    continue
                    
                # 获取相对路径用于构建JSON结构
                rel_path = os.path.relpath(file_path, directory)
                
                # 读取文件内容
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # 解析文件
                    parser = parsers[ext]
                    tree = parser.parse(content)
                    
                    # 处理语法树，提取函数和类
                    items = self.extract_definitions(tree.root_node, content, file_path, ext)
                    
                    if items:
                        # 添加到结果树中
                        self.add_to_result_tree(results, rel_path, items)
                        
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
        self.repo_code_structure = results
        return results

    def extract_definitions(self, node, content, file_path, file_type):
        """提取节点中的函数和类定义，包括源代码"""
        items = []
        
        def get_node_text(node):
            """获取节点的源代码文本"""
            return content[node.start_byte:node.end_byte].decode('utf8')
        
        # 根据不同语言处理不同的节点类型
        if file_type in ['tsx', 'ts', 'js']:
            # 提取函数定义
            if node.type == 'function_declaration' or node.type == 'method_definition':
                name = None
                for child in node.children:
                    if child.type == 'identifier':
                        name = child.text.decode('utf8')
                        break
                
                if name:
                    items.append({
                        'type': 'function',
                        'name': name,
                        'code': get_node_text(node),
                        'file': os.path.basename(file_path)
                    })
            
            # 提取类定义
            elif node.type == 'class_declaration':
                name = None
                for child in node.children:
                    if child.type == 'identifier':
                        name = child.text.decode('utf8')
                        break
                        
                if name:
                    items.append({
                        'type': 'class',
                        'name': name,
                        'code': get_node_text(node),
                        'file': os.path.basename(file_path)
                    })
        
        elif file_type == 'py':
            # 提取Python函数定义
            if node.type == 'function_definition':
                name = None
                for child in node.children:
                    if child.type == 'identifier':
                        name = child.text.decode('utf8')
                        break
                        
                if name:
                    items.append({
                        'type': 'function',
                        'name': name,
                        'code': get_node_text(node),
                        'file': os.path.basename(file_path)
                    })
            
            # 提取Python类定义
            elif node.type == 'class_definition':
                name = None
                for child in node.children:
                    if child.type == 'identifier':
                        name = child.text.decode('utf8')
                        break
                        
                if name:
                    items.append({
                        'type': 'class',
                        'name': name,
                        'code': get_node_text(node),
                        'file': os.path.basename(file_path)
                    })
        
        # 递归处理所有子节点，收集结果
        for child in node.children:
            items.extend(self.extract_definitions(child, content, file_path, file_type))
        
        return items

    def add_to_result_tree(self, results, rel_path, items):
        """将提取的项添加到结果树中"""
        # 按照路径分割文件路径
        path_parts = Path(rel_path).parts
        
        # 沿着路径在结果树中导航
        current = results
        for part in path_parts[:-1]:  # 最后一部分是文件名，单独处理
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # 文件名下存储所有函数和类
        file_name = path_parts[-1]
        if file_name not in current:
            current[file_name] = []
        
        # 添加函数和类
        current[file_name].extend(items)

    def load_models(self):
        """
        加载codet5+模型和令牌。
        """
        print(f"Using device: {self.device}")
        
        # 负载令牌和型号
        self.tokenizer = RobertaTokenizer.from_pretrained(self.model_name)
        self.model = T5EncoderModel.from_pretrained(self.model_name).to(self.device)
        self.model.eval()  # 设置为评估模式
    
    def encode_text(self, text, max_length=512):
        """
        将文本转换为嵌入向量。
        
        Args:
            text (str): 要编码的文本
            max_length (int, optional): 编码文本的最大长度
            
        Returns:
            torch.Tensor: 嵌入向量
        """
        with torch.no_grad():
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                max_length=max_length, 
                padding="max_length", 
                truncation=True
            ).to(self.device)
            
            outputs = self.model(
                input_ids=inputs.input_ids,
                attention_mask=inputs.attention_mask
            )
            
            # 将最后一个隐藏状态的平均值作为文本嵌入
            embedding = torch.mean(outputs.last_hidden_state, dim=1)
            return embedding
    
    def load_code_from_json(self, json_file):
        """
        Load code from a JSON file.
        
        Args:
            json_file (str): Path to the JSON file
        """
        print(f"Loading code from {json_file}...")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            code_structure = json.load(f)
        
        # 清除以前的信息
        self.code_info = []
        
        # 递归处理JSON结构
        def process_structure(structure, path=""):
            for key, value in structure.items():
                current_path = f"{path}/{key}" if path else key
                
                if isinstance(value, dict):
                    # 如果是目录，请递归过程
                    process_structure(value, current_path)
                elif isinstance(value, list):
                    # 如果是文件，请处理所有功能和类
                    for item in value:
                        code = item.get("code", "")
                        name = item.get("name", "")
                        item_type = item.get("type", "")
                        file = item.get("file", "")
                        
                        if code and name:
                            info = {
                                "path": current_path,
                                "file": file,
                                "name": name,
                                "type": item_type,
                                "code": code
                            }
                            self.code_info.append(info)
        
        # 处理整个结构
        process_structure(code_structure)
        print(f"Found {len(self.code_info)} code blocks.")
    
    def compute_code_embeddings(self, batch_size=128):
        """
        计算所有代码块的嵌入。
        
        Args:
            batch_size (int, optional): 批次尺寸用于处理
        """
        if not self.model or not self.tokenizer:
            self.load_models()
            
        print("Computing embeddings for all code blocks...")
        
        all_embeddings = []
        
        # Use batching for efficiency
        for i in tqdm(range(0, len(self.code_info), batch_size)):
            batch = [item["code"] for item in self.code_info[i:i+batch_size]]
            
            with torch.no_grad():
                inputs = self.tokenizer(
                    batch, 
                    return_tensors="pt", 
                    max_length=512, 
                    padding="max_length", 
                    truncation=True
                ).to(self.device)
                
                outputs = self.model(
                    input_ids=inputs.input_ids,
                    attention_mask=inputs.attention_mask
                )
                
                # Use mean of last hidden state as code embedding
                batch_embeddings = torch.mean(outputs.last_hidden_state, dim=1)
                all_embeddings.append(batch_embeddings.cpu())
        
        # Combine all batch embeddings into a single tensor
        if all_embeddings:
            self.code_embeddings = torch.cat(all_embeddings, dim=0)
            # Normalize embedding vectors
            self.code_embeddings = torch.nn.functional.normalize(self.code_embeddings, p=2, dim=1)
            print(f"Computed embeddings with shape: {self.code_embeddings.shape}")
    
    def find_similar_code(self, query_text, top_k=25):
        """
        查找类似于查询文本的代码块。
        
        Args:
            query_text (str): 查询文本以查找类似的代码
            top_k (int, optional): 返回的大多数相似代码块的数量
            
        Returns:
            list: 包含类似代码块的字典列表
        """
        if self.code_embeddings is None:
            print("No embeddings available. Please compute or load embeddings first.")
            return []
        
        print(f"Finding top {top_k} similar code blocks for query...")
        
        # 计算查询文本的嵌入
        query_embedding = self.encode_text(query_text)
        # 标准化查询嵌入
        query_embedding = torch.nn.functional.normalize(query_embedding, p=2, dim=1)
        
        # 计算相似性得分
        self.code_embeddings = self.code_embeddings.to(self.device)
        similarity_scores = torch.mm(query_embedding, self.code_embeddings.t()).squeeze(0)
        
        # 获取top_k的索引最相似的项目
        if len(similarity_scores.shape) == 0:
            similarity_scores = similarity_scores.unsqueeze(0)
        top_indices = torch.argsort(similarity_scores, descending=True)[:top_k].cpu().numpy()
        
        # 准备结果
        results = []
        for idx in top_indices:
            info = self.code_info[idx]
            score = similarity_scores[idx].item()
            
            result = {
                "path": info["path"],
                "file": info["file"],
                "name": info["name"],
                "type": info["type"],
                "code": info["code"],
                "similarity_score": score
            }
            results.append(result)
        
        return results
    
    def format_code_results(self, results):
        """
        LLM输入的格式代码相似性结果。
        
        Args:
            results (list): 类似代码块的列表
            
        Returns:
            str: 格式的代码结果
        """
        formatted_results = ""
        
        for i, result in enumerate(results):
            formatted_results += f"### Code Block {i+1}\n"
            formatted_results += f"- **Path**: {result['path']}\n"
            formatted_results += f"- **File**: {result['file']}\n"
            formatted_results += f"- **Name**: {result['name']}\n"
            formatted_results += f"- **Type**: {result['type']}\n"
            formatted_results += f"- **Similarity Score**: {result['similarity_score']:.4f}\n"
            formatted_results += f"- **Code**:\n```\n{result['code']}\n```\n\n"
        
        return formatted_results

    def save_results_to_json(self, results, output_file):
        """将结果保存为JSON文件"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    def save_embeddings(self, embeddings_file, info_file=None):
        """保存嵌入向量和代码信息到文件"""
        if self.code_embeddings is None:
            print("No embeddings to save.")
            return
        
        print(f"Saving embeddings to {embeddings_file}...")
        torch.save(self.code_embeddings, embeddings_file)
        
        # 如果提供了info_file，同时保存code_info
        if info_file:
            print(f"Saving code info to {info_file}...")
            # 仅保存必要的信息（不包括代码内容）以减小文件大小
            minimal_info = []
            for item in self.code_info:
                # 复制一份，删除代码内容，代码很长可能会导致文件过大
                info_copy = item.copy()
                info_copy["code"] = info_copy["code"][:100] + "..." if len(info_copy["code"]) > 100 else info_copy["code"]
                minimal_info.append(info_copy)
                
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(minimal_info, f, ensure_ascii=False, indent=2)
            
            # 另存一份完整的信息（包括代码内容）
            full_info_file = info_file.replace('.json', '_full.json')
            with open(full_info_file, 'w', encoding='utf-8') as f:
                json.dump(self.code_info, f, ensure_ascii=False, indent=2)
    
    def load_embeddings(self, embeddings_file, info_file=None):
        """从文件加载嵌入向量和代码信息"""
        print(f"Loading embeddings from {embeddings_file}...")
        try:
            self.code_embeddings = torch.load(embeddings_file, map_location=self.device)
            print(f"Loaded embeddings with shape: {self.code_embeddings.shape}")
            
            # 如果提供了info_file，同时加载code_info
            if info_file and os.path.exists(info_file):
                print(f"Loading code info from {info_file}...")
                with open(info_file, 'r', encoding='utf-8') as f:
                    self.code_info = json.load(f)
                print(f"Loaded info for {len(self.code_info)} code blocks.")
                
                # 检查是否为缩略版本，如果是，尝试加载完整版本
                full_info_file = info_file.replace('.json', '_full.json')
                if os.path.exists(full_info_file):
                    print(f"Loading full code info from {full_info_file}...")
                    with open(full_info_file, 'r', encoding='utf-8') as f:
                        self.code_info = json.load(f)
                    print(f"Loaded full info for {len(self.code_info)} code blocks.")
                
            return True
        except Exception as e:
            print(f"Error loading embeddings: {e}")
            return False

    def run(self):
        """
        运行嵌入任务以生成测试计划。
        
        Returns:
            str: 生成的测试计划
        """
        # 加载模型如果尚未加载
        if not self.model or not self.tokenizer:
            self.load_models()
        

        # 决定是加载现有嵌入还是计算新的嵌入
        embeddings_loaded = False
        if os.path.exists(self.config['Embedding']['load_embedding']):
            embeddings_loaded = self.load_embeddings(self.config['Embedding']['load_embedding'], self.config['Embedding']['info_file'])
        
        # 如果没有加载嵌入或加载失败，则计算新的嵌入
        if not embeddings_loaded:
            print("starting to compute embeddings...")
            # 加载代码
            json_file = os.path.join(self.config['CKG']['project_dir'], "code_structure.json")
            self.load_code_from_json(json_file)
            
            # 计算所有代码的嵌入
            self.compute_code_embeddings()
            
            # 如果指定了保存路径，则保存嵌入
            
            self.save_embeddings(self.config['Embedding']['load_embedding'], self.config['Embedding']['info_file'])
        print("starting to find similar code...")
        similar_code = self.find_similar_code(self.PR_Content, top_k=15)
        
        # 格式化LLM输入的代码结果
        formatted_code_results = self.format_code_results(similar_code)
        
        # 创建提示为生成测试计划
        user_prompt = EMBEDDING_TEST_PLAN_USER_PROMPT.format(
            PR_Content=self.PR_Content,
            summaries=self.PR_Changed_Files,
            Similar_Code=formatted_code_results
        )
        
        # 生成测试计划
        print("starting to generate test plan...")
        test_plan, truncated = self.llm(EMBEDDING_TEST_PLAN_SYSTEM_PROMPT, user_prompt, self.config['Agent']['llm_model'])
        
        trajectory = {}
        trajectory['system_prompt'] = EMBEDDING_TEST_PLAN_SYSTEM_PROMPT
        trajectory['user_prompt'] = user_prompt
        trajectory['react_info'] = []
        if '4. Test Cases' in test_plan:
            react_info = {
                'thought': "",
                'test_plan': test_plan
                }
            trajectory['react_info'].append(react_info)
            trajectory['error_content'] = ""
            trajectory['if_truncated'] = truncated
            # 保存结果
            self.save_result(trajectory)
            return test_plan
        else:
            return None