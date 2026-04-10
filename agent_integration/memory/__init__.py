"""
向量记忆模块 - memory

基于ChromaDB的向量数据库记忆存储。
提供语义搜索和记忆管理功能。
"""

from .vector_store import VectorStore
from .memory_manager import MemoryManager
from .config import MemoryConfig

__all__ = [
    'VectorStore',
    'MemoryManager',
    'MemoryConfig',
]

CHROMADB_AVAILABLE = True
try:
    import chromadb
except ImportError:
    CHROMADB_AVAILABLE = False