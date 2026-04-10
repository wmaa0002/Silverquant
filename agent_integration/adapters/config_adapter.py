"""
配置适配器 - ConfigAdapter实现
"""
import os
from typing import Dict, Any, Optional

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use environment variables directly

try:
    from config.settings import Settings
except ImportError:
    Settings = None


class ConfigAdapter:
    """配置适配器
    
    将项目Settings配置转换为智能体可用的格式。
    """
    
    DEFAULT_LLM_CONFIG = {
        'minimax': {
            'provider': 'minimax',
            'model': 'MiniMax-M2.7',
            'temperature': 0.7,
            'max_tokens': 2048,
        },
        'deepseek': {
            'provider': 'deepseek',
            'model': 'deepseek-chat',
            'temperature': 0.7,
            'max_tokens': 2048,
        }
    }
    
    def __init__(self):
        """初始化配置适配器"""
        self._settings = Settings
    
    def get_agent_config(self) -> Dict[str, Any]:
        """获取智能体配置
        
        Returns:
            智能体配置字典
        """
        config = {
            'providers': list(self.DEFAULT_LLM_CONFIG.keys()),
            'default_provider': 'deepseek',
            'default_model': 'deepseek-chat',
            'temperature': 0.7,
            'max_tokens': 2048,
        }
        
        if self._settings and hasattr(self._settings, 'OPENCLAW_CONFIG'):
            config['openclaw'] = self._settings.OPENCLAW_CONFIG
        
        return config
    
    def get_llm_config(self, provider: str = None) -> Dict[str, Any]:
        """获取LLM配置
        
        Args:
            provider: LLM提供商 (minimax/deepseek)
            
        Returns:
            LLM配置字典
        """
        provider = provider or os.getenv('LLM_PROVIDER', 'deepseek')
        
        if provider in self.DEFAULT_LLM_CONFIG:
            config = self.DEFAULT_LLM_CONFIG[provider].copy()
        else:
            config = self.DEFAULT_LLM_CONFIG['deepseek'].copy()
        
        config['api_key'] = self._get_api_key(provider)
        
        return config
    
    def _get_api_key(self, provider: str) -> Optional[str]:
        """获取API密钥"""
        env_vars = {
            'minimax': 'MINIMAX_API_KEY',
            'deepseek': 'DEEPSEEK_API_KEY',
        }
        
        env_var = env_vars.get(provider)
        if env_var:
            return os.environ.get(env_var)
        
        return None
    
    def get_data_config(self) -> Dict[str, Any]:
        """获取数据源配置
        
        Returns:
            数据源配置字典
        """
        config = {
            'source': 'akshare',
            'rate_limit': 0.1,
            'max_retries': 3,
        }
        
        if self._settings:
            config['source'] = getattr(self._settings, 'DATA_SOURCE', 'akshare')
            config['rate_limit'] = getattr(self._settings, 'AKSHARE_RATE_LIMIT', 0.1)
            config['max_retries'] = getattr(self._settings, 'AKSHARE_MAX_RETRIES', 3)
            config['database_path'] = str(getattr(self._settings, 'DATABASE_PATH', ''))
        
        return config
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置
        
        Returns:
            数据库配置字典
        """
        config = {
            'path': 'data/Astock3.duckdb',
        }
        
        if self._settings:
            config['path'] = str(getattr(self._settings, 'DATABASE_PATH', config['path']))
        
        return config
    
    def get_trading_config(self) -> Dict[str, Any]:
        """获取交易配置
        
        Returns:
            交易配置字典
        """
        config = {
            'default_initial_cash': 100000.0,
            'default_commission': 0.0003,
            'default_stop_loss': 0.05,
            'default_take_profit': 0.10,
        }
        
        if self._settings:
            config['default_initial_cash'] = getattr(self._settings, 'DEFAULT_INITIAL_CASH', 100000.0)
            config['default_commission'] = getattr(self._settings, 'DEFAULT_COMMISSION', 0.0003)
            config['default_stop_loss'] = getattr(self._settings, 'DEFAULT_STOP_LOSS', 0.05)
            config['default_take_profit'] = getattr(self._settings, 'DEFAULT_TAKE_PROFIT', 0.10)
        
        return config


def get_default_config() -> ConfigAdapter:
    """获取默认配置适配器"""
    return ConfigAdapter()