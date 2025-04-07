import os
import json
import torch
import numpy as np
from transformers import T5EncoderModel, RobertaTokenizer
from tqdm import tqdm
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
        self.model_name = "Salesforce/codet5p-base"
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = None
        self.model = None
        self.code_embeddings = None
        self.code_info = []
    
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
    
    def compute_code_embeddings(self, batch_size=16):
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
    
    def run(self):
        """
        运行嵌入任务以生成测试计划。
        
        Returns:
            str: 生成的测试计划
        """
        # 加载模型如果尚未加载
        if not self.model or not self.tokenizer:
            self.load_models()
        
        # 来自JSON文件的加载代码（使用配置中的路径）
        json_file = os.path.join(self.config['CKG']['project_dir'], 'code_structure.json')
        self.load_code_from_json(json_file)
        
        # 计算嵌入
        self.compute_code_embeddings()
        
        # 找到与PR内容的类似代码块
        similar_code = self.find_similar_code(self.PR_Content, top_k=25)
        
        # 格式化LLM输入的代码结果
        formatted_code_results = self.format_code_results(similar_code)
        
        # 创建提示为生成测试计划
        user_prompt = EMBEDDING_TEST_PLAN_USER_PROMPT.format(
            PR_Content=self.PR_Content,
            PR_Changed_Files=self.PR_Changed_Files,
            Similar_Code=formatted_code_results
        )
        
        # 生成测试计划
        test_plan = self.llm(EMBEDDING_TEST_PLAN_SYSTEM_PROMPT, user_prompt, self.config['Agent']['llm_model'])
        
        # 保存结果
        self.save_result(user_prompt, test_plan)
        
        return test_plan