"""
向量存储 - VectorStore
"""
import os
from typing import Dict, Any, List, Optional

CHROMADB_AVAILABLE = True
try:
    import chromadb
except ImportError:
    CHROMADB_AVAILABLE = False


class VectorStore:
    """ChromaDB向量存储包装器
    
    提供语义搜索功能。
    如果ChromaDB未安装，返回空实现。
    """
    
    def __init__(
        self,
        persist_directory: str = 'data/agent_memory',
        collection_name: str = 'analysis'
    ):
        """初始化向量存储
        
        Args:
            persist_directory: 持久化目录
            collection_name: 默认collection名称
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._available = CHROMADB_AVAILABLE
        
        if self._available:
            self._init_chroma()
        else:
            print("警告: ChromaDB未安装，向量存储功能不可用")
    
    def _init_chroma(self):
        """初始化ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            os.makedirs(self.persist_directory, exist_ok=True)
            
            self._client = chromadb.Client(Settings(
                persist_directory=self.persist_directory,
                anonymized_telemetry=False
            ))
            
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={'description': 'Agent analysis memories'}
            )
            
        except Exception as e:
            print(f"ChromaDB初始化失败: {e}")
            self._available = False
    
    def add(
        self,
        texts: List[str],
        embeddings: List[List[float]] = None,
        metadatas: List[Dict] = None,
        ids: List[str] = None,
        collection: str = None
    ) -> bool:
        """添加向量数据
        
        Args:
            texts: 文本列表
            embeddings: 向量列表（可选）
            metadatas: 元数据列表
            ids: ID列表
            collection: collection名称
            
        Returns:
            是否成功
        """
        if not self._available:
            return False
        
        try:
            coll = self._get_collection(collection)
            if coll is None:
                return False
            
            if ids is None:
                ids = [f"mem_{i}" for i in range(len(texts))]
            
            coll.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            
            return True
            
        except Exception as e:
            print(f"添加向量数据失败: {e}")
            return False
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        where_filter: Dict = None,
        collection: str = None
    ) -> List[Dict[str, Any]]:
        """相似性搜索
        
        Args:
            query: 查询文本
            n_results: 返回数量
            where_filter: 过滤条件
            collection: collection名称
            
        Returns:
            搜索结果列表
        """
        if not self._available:
            return []
        
        try:
            coll = self._get_collection(collection)
            if coll is None:
                return []
            
            results = coll.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )
            
            return self._format_results(results)
            
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def get_by_filter(
        self,
        where_filter: Dict,
        collection: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """根据过滤条件获取数据
        
        Args:
            where_filter: 过滤条件
            collection: collection名称
            limit: 数量限制
            
        Returns:
            数据列表
        """
        if not self._available:
            return []
        
        try:
            coll = self._get_collection(collection)
            if coll is None:
                return []
            
            results = coll.get(
                where=where_filter,
                limit=limit
            )
            
            return self._format_get_results(results)
            
        except Exception as e:
            print(f"获取数据失败: {e}")
            return []
    
    def delete(
        self,
        ids: List[str] = None,
        where_filter: Dict = None,
        collection: str = None
    ) -> bool:
        """删除数据
        
        Args:
            ids: ID列表
            where_filter: 过滤条件
            collection: collection名称
            
        Returns:
            是否成功
        """
        if not self._available:
            return False
        
        try:
            coll = self._get_collection(collection)
            if coll is None:
                return False
            
            coll.delete(ids=ids, where=where_filter)
            return True
            
        except Exception as e:
            print(f"删除数据失败: {e}")
            return False
    
    def count(self, collection: str = None) -> int:
        """获取collection中的数据数量
        
        Args:
            collection: collection名称
            
        Returns:
            数据数量
        """
        if not self._available:
            return 0
        
        try:
            coll = self._get_collection(collection)
            if coll is None:
                return 0
            
            return coll.count()
            
        except Exception as e:
            print(f"获取数量失败: {e}")
            return 0
    
    def _get_collection(self, collection_name: str = None) -> Any:
        """获取collection"""
        if not self._available or self._client is None:
            return None
        
        if collection_name is None:
            return self._collection
        
        try:
            return self._client.get_collection(name=collection_name)
        except:
            return None
    
    def _format_results(self, results: Dict) -> List[Dict[str, Any]]:
        """格式化搜索结果"""
        formatted = []
        
        if not results or 'documents' not in results:
            return formatted
        
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]
        ids = results.get('ids', [[]])[0]
        
        for i, doc in enumerate(documents):
            formatted.append({
                'id': ids[i] if i < len(ids) else f'result_{i}',
                'document': doc,
                'metadata': metadatas[i] if i < len(metadatas) else {},
                'distance': distances[i] if i < len(distances) else 0.0
            })
        
        return formatted
    
    def _format_get_results(self, results: Dict) -> List[Dict[str, Any]]:
        """格式化get结果"""
        formatted = []
        
        if not results or 'documents' not in results:
            return formatted
        
        documents = results.get('documents', [])
        metadatas = results.get('metadatas', [])
        ids = results.get('ids', [])
        
        for i, doc in enumerate(documents):
            formatted.append({
                'id': ids[i] if i < len(ids) else f'result_{i}',
                'document': doc,
                'metadata': metadatas[i] if i < len(metadatas) else {}
            })
        
        return formatted
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self._available