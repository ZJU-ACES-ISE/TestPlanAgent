import json
import torch
import numpy as np
from transformers import T5EncoderModel, RobertaTokenizer
from tqdm import tqdm
import os
from pathlib import Path
import argparse
import time

class CodeSimilaritySearch:
    def __init__(self, model_name="Salesforce/codet5p-base"):
        """初始化CodeT5+模型和分词器"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # 加载模型和分词器
        self.tokenizer = RobertaTokenizer.from_pretrained(model_name)
        self.model = T5EncoderModel.from_pretrained(model_name).to(self.device)
        self.model.eval()  # 设置为评估模式
        
        # 存储代码嵌入
        self.code_embeddings = None
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
        """从JSON文件加载代码"""
        print(f"Loading code from {json_file}...")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            code_structure = json.load(f)
        
        # 清空之前的信息
        self.code_info = []
        
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
        start_time = time.time()
        
        all_embeddings = []
        
        # 使用批处理来提高效率
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
                
                # 取最后一层隐藏状态的平均值作为代码嵌入
                batch_embeddings = torch.mean(outputs.last_hidden_state, dim=1)
                all_embeddings.append(batch_embeddings.cpu())
        
        # 将所有批次的嵌入合并为一个张量
        if all_embeddings:
            self.code_embeddings = torch.cat(all_embeddings, dim=0)
            # 标准化嵌入向量
            self.code_embeddings = torch.nn.functional.normalize(self.code_embeddings, p=2, dim=1)
            print(f"Computed embeddings with shape: {self.code_embeddings.shape}")
            print(f"Embedding computation took {time.time() - start_time:.2f} seconds")
    
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
    
    def find_similar_code(self, query_text, top_k=25):
        """根据查询文本查找最相似的代码块"""
        if self.code_embeddings is None:
            print("No embeddings available. Please compute or load embeddings first.")
            return []
        
        print(f"Finding top {top_k} similar code blocks for query...")
        
        # 为查询文本计算嵌入
        query_embedding = self.encode_text(query_text)
        # 标准化查询嵌入
        query_embedding = torch.nn.functional.normalize(query_embedding, p=2, dim=1)
        
        # 计算相似度分数
        self.code_embeddings = self.code_embeddings.to(self.device)
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
    parser.add_argument("--json_file", type=str, help="Path to the JSON file with code structure")
    parser.add_argument("--pr_description", type=str, help="PR description or path to a text file with PR description")
    parser.add_argument("--output", type=str, default="similar_code_results.json", help="Path to output JSON file")
    parser.add_argument("--top_k", type=int, default=25, help="Number of most similar code blocks to return")
    parser.add_argument("--save_embeddings", type=str, help="Path to save embeddings")
    parser.add_argument("--load_embeddings", type=str, help="Path to load embeddings from")
    parser.add_argument("--info_file", type=str, help="Path to save/load code info")
    
    args = parser.parse_args()
    
    # 初始化代码相似度搜索
    searcher = CodeSimilaritySearch()
    
    # 决定是加载现有嵌入还是计算新的嵌入
    embeddings_loaded = False
    if args.load_embeddings and os.path.exists(args.load_embeddings):
        embeddings_loaded = searcher.load_embeddings(args.load_embeddings, args.info_file)
    
    # 如果没有加载嵌入或加载失败，则计算新的嵌入
    if not embeddings_loaded:
        if not args.json_file:
            print("Error: Either --load_embeddings or --json_file must be specified.")
            return
        
        # 加载代码
        searcher.load_code_from_json(args.json_file)
        
        # 计算所有代码的嵌入
        searcher.compute_code_embeddings()
        
        # 如果指定了保存路径，则保存嵌入
        if args.save_embeddings:
            searcher.save_embeddings(args.save_embeddings, args.info_file)
    
    # 只有在提供了PR描述时才进行相似度搜索
    if args.pr_description:
        # 获取PR描述
        if os.path.isfile(args.pr_description):
            with open(args.pr_description, 'r', encoding='utf-8') as f:
                pr_description = f.read()
        else:
            pr_description = args.pr_description
        
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