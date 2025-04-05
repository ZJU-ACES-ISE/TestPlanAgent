import json
import torch
import numpy as np
from transformers import T5EncoderModel, RobertaTokenizer
from tqdm import tqdm
import os
from pathlib import Path
import argparse

class CodeSimilaritySearch:
    def __init__(self, model_name="Salesforce/codet5p-110m-embedding"):
        """初始化CodeT5+模型和分词器"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # 加载模型和分词器
        self.tokenizer = RobertaTokenizer.from_pretrained(model_name)
        self.model = T5EncoderModel.from_pretrained(model_name).to(self.device)
        self.model.eval()  # 设置为评估模式
        
        # 存储代码嵌入
        self.code_embeddings = []
        self.code_info = []
    
    def encode_text(self, text, max_length=512):
        """将文本转换为嵌入向量"""
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
            
            # 取最后一层隐藏状态的平均值作为文本嵌入
            embedding = torch.mean(outputs.last_hidden_state, dim=1)
            return embedding
    
    def load_code_from_json(self, json_file):
        """从JSON文件加载代码并计算嵌入"""
        print(f"Loading code from {json_file}...")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            code_structure = json.load(f)
        
        # 递归函数来处理JSON结构
        def process_structure(structure, path=""):
            for key, value in structure.items():
                current_path = f"{path}/{key}" if path else key
                
                if isinstance(value, dict):
                    # 如果是目录，递归处理
                    process_structure(value, current_path)
                elif isinstance(value, list):
                    # 如果是文件，处理所有函数和类
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
        """为所有代码块计算嵌入向量"""
        print("Computing embeddings for all code blocks...")
        
        self.code_embeddings = []
        
        # 使用批处理来提高效率
        for i in tqdm(range(0, len(self.code_info), batch_size), desc="Processing batches", unit="batch"):
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
                
                # 取最后一层隐藏状态的平均值作为代码嵌入
                batch_embeddings = torch.mean(outputs.last_hidden_state, dim=1)
                self.code_embeddings.append(batch_embeddings)
        
        # 将所有批次的嵌入合并为一个张量
        if self.code_embeddings:
            self.code_embeddings = torch.cat(self.code_embeddings, dim=0)
            # 标准化嵌入向量
            self.code_embeddings = torch.nn.functional.normalize(self.code_embeddings, p=2, dim=1)
            print(f"Computed embeddings with shape: {self.code_embeddings.shape}")
    
    def find_similar_code(self, query_text, top_k=25):
        """根据查询文本查找最相似的代码块"""
        print(f"Finding top {top_k} similar code blocks for query: {query_text[:100]}...")
        
        # 为查询文本计算嵌入
        query_embedding = self.encode_text(query_text)
        # 标准化查询嵌入
        query_embedding = torch.nn.functional.normalize(query_embedding, p=2, dim=1)
        
        # 计算相似度分数
        similarity_scores = torch.mm(query_embedding, self.code_embeddings.t()).squeeze(0)
        
        # 获取相似度最高的top_k个索引
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

def main():
    parser = argparse.ArgumentParser(description="Find code similar to PR description using CodeT5+")
    parser.add_argument("--json_file", type=str, required=True, help="Path to the JSON file with code structure")
    # parser.add_argument("--pr_description", type=str, required=True, help="PR description or path to a text file with PR description")
    parser.add_argument("--output", type=str, default="similar_code_results.json", help="Path to output JSON file")
    parser.add_argument("--top_k", type=int, default=25, help="Number of most similar code blocks to return")
    
    args = parser.parse_args()
    
    # 初始化代码相似度搜索
    searcher = CodeSimilaritySearch()
    
    # 加载代码
    searcher.load_code_from_json(args.json_file)
    
    # 计算所有代码的嵌入
    searcher.compute_code_embeddings()
    
    # 获取PR描述
    # if os.path.isfile(args.pr_description):
    #     with open(args.pr_description, 'r', encoding='utf-8') as f:
    #         pr_description = f.read()
    # else:
    pr_description = ""
    
    # 查找相似代码
    results = searcher.find_similar_code(pr_description, args.top_k)
    
    # 保存结果
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Results saved to {args.output}")
    
    # 打印前5个结果
    print("\nTop 5 most similar code blocks:")
    for i, result in enumerate(results[:5]):
        print(f"{i+1}. {result['type']} {result['name']} (Score: {result['similarity_score']:.4f})")
        print(f"   Path: {result['path']}")
        print(f"   Code snippet: {result['code'][:100]}...\n")

if __name__ == "__main__":
    main()