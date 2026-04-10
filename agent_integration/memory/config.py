"""
记忆配置 - MemoryConfig
"""
import os


class MemoryConfig:
    """记忆模块配置"""
    
    PERSIST_DIRECTORY = 'data/agent_memory'
    EMBEDDING_MODEL = 'chroma'
    COLLECTION_ANALYSIS = 'analysis'
    COLLECTION_NEWS = 'news'
    COLLECTION_RESEARCH = 'research'
    MAX_MEMORIES = 1000
    DEFAULT_SEARCH_LIMIT = 5
    MEMORY_TTL_DAYS = 90
    
    @classmethod
    def load_from_env(cls):
        """从环境变量加载配置"""
        cls.PERSIST_DIRECTORY = os.getenv('MEMORY_PERSIST_DIR', cls.PERSIST_DIRECTORY)
        cls.EMBEDDING_MODEL = os.getenv('MEMORY_EMBEDDING_MODEL', cls.EMBEDDING_MODEL)
        cls.COLLECTION_ANALYSIS = os.getenv('MEMORY_COLLECTION_ANALYSIS', cls.COLLECTION_ANALYSIS)
        cls.COLLECTION_NEWS = os.getenv('MEMORY_COLLECTION_NEWS', cls.COLLECTION_NEWS)
        cls.COLLECTION_RESEARCH = os.getenv('MEMORY_COLLECTION_RESEARCH', cls.COLLECTION_RESEARCH)
        
        if os.getenv('MEMORY_MAX_MEMORIES'):
            cls.MAX_MEMORIES = int(os.getenv('MEMORY_MAX_MEMORIES'))
        
        if os.getenv('MEMORY_TTL_DAYS'):
            cls.MEMORY_TTL_DAYS = int(os.getenv('MEMORY_TTL_DAYS'))
        
        return cls