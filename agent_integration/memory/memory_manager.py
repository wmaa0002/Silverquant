"""
记忆管理器 - MemoryManager
"""
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from .vector_store import VectorStore
from .config import MemoryConfig


class MemoryManager:
    """记忆管理器
    
    负责管理分析结果的向量存储和检索。
    """
    
    def __init__(self, persist_directory: str = None):
        """初始化记忆管理器
        
        Args:
            persist_directory: 持久化目录
        """
        config = MemoryConfig.load_from_env()
        
        self.persist_directory = persist_directory or config.PERSIST_DIRECTORY
        self.vector_store = VectorStore(
            persist_directory=self.persist_directory,
            collection_name=config.COLLECTION_ANALYSIS
        )
        
        self.llm = None
    
    def set_llm(self, llm):
        """设置LLM适配器（用于生成文本摘要）
        
        Args:
            llm: LLM适配器实例
        """
        self.llm = llm
    
    def save_analysis_result(
        self,
        symbol: str,
        trade_date: str,
        result: Dict[str, Any],
        embedding_text: str = None
    ) -> bool:
        """保存分析结果到向量存储
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期
            result: 分析结果
            embedding_text: 用于embedding的文本（可选）
            
        Returns:
            是否成功
        """
        if not self.vector_store.is_available():
            return False
        
        if embedding_text is None:
            embedding_text = self._create_embedding_text(symbol, trade_date, result)
        
        memory_id = f"{symbol}_{trade_date}_{uuid.uuid4().hex[:8]}"
        
        metadata = {
            'symbol': symbol,
            'trade_date': trade_date,
            'created_at': datetime.now().isoformat(),
            'decision': result.get('final_decision', ''),
            'confidence': result.get('confidence', 0.0),
            'type': 'analysis'
        }
        
        try:
            success = self.vector_store.add(
                texts=[embedding_text],
                metadatas=[metadata],
                ids=[memory_id],
                collection=MemoryConfig.COLLECTION_ANALYSIS
            )
            
            return success
            
        except Exception as e:
            print(f"保存分析结果失败: {e}")
            return False
    
    def search_related(
        self,
        symbol: str = None,
        query: str = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """搜索相关记忆
        
        Args:
            symbol: 股票代码过滤
            query: 查询文本
            limit: 返回数量
            
        Returns:
            相关记忆列表
        """
        if not self.vector_store.is_available():
            return []
        
        if query is None:
            query = f"{symbol} 分析" if symbol else "股票分析"
        
        where_filter = None
        if symbol:
            where_filter = {'symbol': symbol}
        
        try:
            results = self.vector_store.search(
                query=query,
                n_results=limit,
                where_filter=where_filter,
                collection=MemoryConfig.COLLECTION_ANALYSIS
            )
            
            return self._format_search_results(results)
            
        except Exception as e:
            print(f"搜索记忆失败: {e}")
            return []
    
    def get_history(
        self,
        symbol: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取分析历史
        
        Args:
            symbol: 股票代码
            limit: 返回数量
            
        Returns:
            历史记录列表
        """
        if not self.vector_store.is_available():
            return []
        
        where_filter = None
        if symbol:
            where_filter = {'symbol': symbol}
        
        try:
            results = self.vector_store.get_by_filter(
                where_filter=where_filter,
                collection=MemoryConfig.COLLECTION_ANALYSIS,
                limit=limit
            )
            
            return results
            
        except Exception as e:
            print(f"获取历史失败: {e}")
            return []
    
    def clear_old(self, days: int = None) -> int:
        """清理旧记忆
        
        Args:
            days: 保留最近N天的记忆
            
        Returns:
            删除数量
        """
        if not self.vector_store.is_available():
            return 0
        
        if days is None:
            days = MemoryConfig.MEMORY_TTL_DAYS
        
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()
        
        deleted_count = 0
        
        try:
            all_results = self.vector_store.get_by_filter(
                collection=MemoryConfig.COLLECTION_ANALYSIS,
                limit=1000
            )
            
            ids_to_delete = []
            for result in all_results:
                created_at = result.get('metadata', {}).get('created_at', '')
                if created_at and created_at < cutoff_str:
                    ids_to_delete.append(result['id'])
            
            if ids_to_delete:
                self.vector_store.delete(
                    ids=ids_to_delete,
                    collection=MemoryConfig.COLLECTION_ANALYSIS
                )
                deleted_count = len(ids_to_delete)
            
            return deleted_count
            
        except Exception as e:
            print(f"清理旧记忆失败: {e}")
            return deleted_count
    
    def save_news_memory(
        self,
        symbol: str,
        news_text: str,
        sentiment: str = None,
        metadata: Dict = None
    ) -> bool:
        """保存新闻记忆
        
        Args:
            symbol: 股票代码
            news_text: 新闻文本
            sentiment: 情感分类
            metadata: 额外元数据
            
        Returns:
            是否成功
        """
        if not self.vector_store.is_available():
            return False
        
        memory_id = f"news_{symbol}_{uuid.uuid4().hex[:8]}"
        
        meta = {
            'symbol': symbol,
            'created_at': datetime.now().isoformat(),
            'type': 'news'
        }
        
        if sentiment:
            meta['sentiment'] = sentiment
        
        if metadata:
            meta.update(metadata)
        
        try:
            return self.vector_store.add(
                texts=[news_text],
                metadatas=[meta],
                ids=[memory_id],
                collection=MemoryConfig.COLLECTION_NEWS
            )
            
        except Exception as e:
            print(f"保存新闻记忆失败: {e}")
            return False
    
    def search_news(
        self,
        symbol: str = None,
        query: str = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """搜索相关新闻记忆
        
        Args:
            symbol: 股票代码
            query: 查询文本
            limit: 返回数量
            
        Returns:
            新闻记忆列表
        """
        if not self.vector_store.is_available():
            return []
        
        if query is None:
            query = f"{symbol} 新闻" if symbol else "新闻"
        
        where_filter = None
        if symbol:
            where_filter = {'symbol': symbol}
        
        try:
            results = self.vector_store.search(
                query=query,
                n_results=limit,
                where_filter=where_filter,
                collection=MemoryConfig.COLLECTION_NEWS
            )
            
            return self._format_search_results(results)
            
        except Exception as e:
            print(f"搜索新闻记忆失败: {e}")
            return []
    
    def _create_embedding_text(
        self,
        symbol: str,
        trade_date: str,
        result: Dict[str, Any]
    ) -> str:
        """创建embedding文本
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期
            result: 分析结果
            
        Returns:
            用于embedding的文本
        """
        lines = [
            f"股票: {symbol}",
            f"日期: {trade_date}",
            f"决策: {result.get('final_decision', 'N/A')}",
            f"置信度: {result.get('confidence', 0.0):.2f}",
        ]
        
        decision = result.get('final_decision', '')
        if '买入' in decision:
            lines.append("倾向于买入")
        elif '卖出' in decision:
            lines.append("倾向于卖出")
        else:
            lines.append("建议观望")
        
        if 'reports' in result:
            reports = result['reports']
            if isinstance(reports, dict):
                for key, value in reports.items():
                    if value:
                        lines.append(f"{key}: {str(value)[:100]}")
        
        return ' '.join(lines)
    
    def _format_search_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """格式化搜索结果"""
        formatted = []
        
        for r in results:
            meta = r.get('metadata', {})
            formatted.append({
                'id': r.get('id', ''),
                'document': r.get('document', ''),
                'symbol': meta.get('symbol', ''),
                'trade_date': meta.get('trade_date', ''),
                'created_at': meta.get('created_at', ''),
                'decision': meta.get('decision', ''),
                'confidence': meta.get('confidence', 0.0),
                'distance': r.get('distance', 0.0)
            })
        
        return formatted
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.vector_store.is_available() if self.vector_store else False