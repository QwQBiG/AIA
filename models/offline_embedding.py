
import os
import numpy as np
from typing import List

class OfflineEmbeddingModel:
    """简单的离线嵌入模型备用方案"""
    
    def __init__(self):
        self.dimension = 384  # 与 all-MiniLM-L6-v2 相同
        
    def encode(self, texts: List[str]) -> np.ndarray:
        """生成简单的文本嵌入向量"""
        embeddings = []
        for text in texts:
            # 基于文本哈希生成确定性向量
            hash_val = hash(text.lower())
            np.random.seed(abs(hash_val) % (2**32))
            embedding = np.random.normal(0, 1, self.dimension)
            embedding = embedding / np.linalg.norm(embedding)  # 归一化
            embeddings.append(embedding)
        return np.array(embeddings)

# 导出备用模型
offline_model = OfflineEmbeddingModel()
