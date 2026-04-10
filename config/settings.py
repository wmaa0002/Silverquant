"""
配置管理 - 集中管理项目配置
"""
import os
from pathlib import Path
from typing import Dict, Any
import json

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    """项目配置类"""
    
    # 项目路径
    PROJECT_ROOT = Path(__file__).parent.parent
    
    # 数据库配置
    DATABASE_PATH = PROJECT_ROOT / 'data' / 'Astock3.duckdb'
    
    # 数据目录
    DATA_DIR = PROJECT_ROOT / 'data'
    RAW_DATA_DIR = DATA_DIR / 'raw'
    PROCESSED_DATA_DIR = DATA_DIR / 'processed'
    
    # 回测结果目录
    BACKTEST_RESULTS_DIR = PROJECT_ROOT / 'results'
    
    # akshare配置
    AKSHARE_RATE_LIMIT = 0.1  # API调用间隔（秒）
    AKSHARE_MAX_RETRIES = 3   # 最大重试次数
    
    # 数据源配置
    DATA_SOURCE = 'baostock'  # 数据源: 'akshare' 或 'baostock'
    
    # tushare配置
    TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN')  # 从环境变量读取
    DATA_SOURCE_PRIORITY = ['tushare', 'baostock']  # 数据源优先级顺序
    FAILOVER_ERROR_RATE_THRESHOLD = 0.30  # 故障转移错误率阈值
    FAILOVER_RESPONSE_TIME_THRESHOLD = 10.0  # 故障转移响应时间阈值（秒）
    HEALTH_CHECK_INTERVAL = 300  # 健康检查间隔（秒）
    
    # 回测默认参数
    DEFAULT_INITIAL_CASH = 100000.0
    DEFAULT_COMMISSION = 0.0003
    DEFAULT_STAMP_DUTY = 0.001
    DEFAULT_SLIPPAGE = 0.001
    
    # 策略默认参数
    DEFAULT_STOP_LOSS = 0.05
    DEFAULT_TAKE_PROFIT = 0.10
    DEFAULT_POSITION_PCT = 0.95
    DEFAULT_MAX_POSITIONS = 10
    
    # 数据更新配置
    DATA_UPDATE_START_DATE = '2020-01-01'
    PRICE_HISTORY_DAYS = 120  # 计算技术指标需要的历史数据天数
    
    # 多因子配置
    DEFAULT_FACTOR_WEIGHTS = {
        'pe_ttm': 0.15,
        'pb': 0.15,
        'roe': 0.20,
        'revenue_growth_yoy': 0.20,
        'rsi_24': 0.15,
        'macd_dif': 0.15,
    }
    
    DEFAULT_FACTOR_DIRECTION = {
        'pe_ttm': -1,  # 低估值优先
        'pb': -1,
        'roe': 1,      # 高ROE优先
        'revenue_growth_yoy': 1,  # 高成长优先
        'rsi_24': -1,  # 低RSI优先（超卖）
        'macd_dif': 1, # MACD正值优先
    }
    
    # 市值分组阈值（亿元）
    CAP_GROUP_THRESHOLDS = {
        'large': 1000,    # 大盘: >1000亿
        'mid': 300,       # 中盘: 300-1000亿
        'small': 100,     # 小盘: 100-300亿
        'micro': 0,       # 微盘: <100亿
    }
    
    # OpenClaw Agent配置
    OPENCLAW_CONFIG = {
        'enabled': True,
        'model': 'claude-3-5-sonnet-20241022',
        'temperature': 0.7,
        'max_tokens': 4096,
    }
    
    # 日志配置
    LOG_LEVEL = 'INFO'
    LOG_DIR = PROJECT_ROOT / 'logs'
    
    @classmethod
    def ensure_directories(cls):
        """确保所有目录存在"""
        directories = [
            cls.DATA_DIR,
            cls.RAW_DATA_DIR,
            cls.PROCESSED_DATA_DIR,
            cls.BACKTEST_RESULTS_DIR,
            cls.LOG_DIR,
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load_from_env(cls):
        """从环境变量加载配置"""
        # 数据库路径
        db_path = os.getenv('QUANT_DB_PATH')
        if db_path:
            cls.DATABASE_PATH = Path(db_path)
        
        # 日志级别
        log_level = os.getenv('QUANT_LOG_LEVEL')
        if log_level:
            cls.LOG_LEVEL = log_level
        
        # 初始资金
        initial_cash = os.getenv('QUANT_INITIAL_CASH')
        if initial_cash:
            cls.DEFAULT_INITIAL_CASH = float(initial_cash)
    
    @classmethod
    def load_from_file(cls, config_file: str):
        """从JSON文件加载配置"""
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"配置文件不存在: {config_file}")
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 应用配置
        for key, value in config.items():
            if hasattr(cls, key):
                setattr(cls, key, value)
        
        print(f"配置已从 {config_file} 加载")
    
    @classmethod
    def save_to_file(cls, config_file: str):
        """保存配置到JSON文件"""
        config = {
            'DATABASE_PATH': str(cls.DATABASE_PATH),
            'DEFAULT_INITIAL_CASH': cls.DEFAULT_INITIAL_CASH,
            'DEFAULT_COMMISSION': cls.DEFAULT_COMMISSION,
            'DEFAULT_STOP_LOSS': cls.DEFAULT_STOP_LOSS,
            'DEFAULT_FACTOR_WEIGHTS': cls.DEFAULT_FACTOR_WEIGHTS,
            'DEFAULT_FACTOR_DIRECTION': cls.DEFAULT_FACTOR_DIRECTION,
            'CAP_GROUP_THRESHOLDS': cls.CAP_GROUP_THRESHOLDS,
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"配置已保存到 {config_file}")
    
    @classmethod
    def get_database_url(cls) -> str:
        """获取数据库连接URL"""
        return str(cls.DATABASE_PATH)
    
    @classmethod
    def get_cap_group(cls, market_cap: float) -> str:
        """
        根据市值判断分组
        
        Args:
            market_cap: 市值（亿元）
        
        Returns:
            市值分组: large/mid/small/micro
        """
        if market_cap >= cls.CAP_GROUP_THRESHOLDS['large']:
            return 'large'
        elif market_cap >= cls.CAP_GROUP_THRESHOLDS['mid']:
            return 'mid'
        elif market_cap >= cls.CAP_GROUP_THRESHOLDS['small']:
            return 'small'
        else:
            return 'micro'


# 初始化配置
Settings.ensure_directories()
Settings.load_from_env()
