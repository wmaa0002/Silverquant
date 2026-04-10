"""
项目初始化脚本
创建数据库、下载基础数据、验证环境
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import subprocess
import importlib
from database.db_manager import DatabaseManager
from config.settings import Settings


def check_dependencies():
    """检查必要的依赖包"""
    print("="*50)
    print("检查依赖包...")
    print("="*50)
    
    required_packages = [
        'duckdb',
        'pandas',
        'numpy',
        'akshare',
        'backtrader',
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"  {package}: 已安装")
        except ImportError:
            print(f"  {package}: 未安装")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n缺少以下依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    
    print("\n所有依赖包已安装")
    return True


def init_database():
    """初始化数据库"""
    print("\n" + "="*50)
    print("初始化数据库...")
    print("="*50)
    
    try:
        db = DatabaseManager()
        print(f"数据库路径: {Settings.DATABASE_PATH}")
        print("数据库表结构已创建")
        db.close()
        return True
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        return False


def download_stock_list():
    """下载股票基础信息"""
    print("\n" + "="*50)
    print("下载股票基础信息...")
    print("="*50)
    
    try:
        from data.fetchers.stock_fetcher import StockFetcher
        from database.db_manager import DatabaseManager
        
        fetcher = StockFetcher()
        db = DatabaseManager()
        
        print("正在获取股票列表...")
        df = fetcher.get_stock_list()
        
        print(f"获取到 {len(df)} 只股票")
        print("正在保存到数据库...")
        
        db.save_stock_info(df)
        
        print("股票基础信息下载完成")
        return True
        
    except Exception as e:
        print(f"下载股票列表失败: {e}")
        return False


def create_directory_structure():
    """创建项目目录结构"""
    print("\n" + "="*50)
    print("创建目录结构...")
    print("="*50)
    
    directories = [
        'data/raw',
        'data/processed',
        'results',
        'logs',
        'debug/agent',
        'debug/logs',
        'debug/reports',
    ]
    
    for directory in directories:
        path = project_root / directory
        path.mkdir(parents=True, exist_ok=True)
        print(f"  创建目录: {directory}")
    
    print("目录结构创建完成")
    return True


def test_data_connection():
    """测试数据连接"""
    print("\n" + "="*50)
    print("测试数据连接...")
    print("="*50)
    
    try:
        from data.fetchers.stock_fetcher import StockFetcher
        
        fetcher = StockFetcher()
        
        print("测试获取股票列表...")
        df = fetcher.get_stock_list()
        print(f"  成功获取 {len(df)} 只股票")
        
        print("测试获取单只股票数据...")
        test_code = '000001'  # 平安银行
        price_df = fetcher.get_daily_price(test_code, start_date='20240101')
        print(f"  成功获取 {test_code} 的 {len(price_df)} 条数据")
        
        print("数据连接测试通过")
        return True
        
    except Exception as e:
        print(f"数据连接测试失败: {e}")
        return False


def print_project_structure():
    """打印项目结构"""
    print("\n" + "="*50)
    print("项目结构")
    print("="*50)
    
    structure = """
股票策略/
├── config/                 # 配置管理
│   ├── __init__.py
│   └── settings.py        # 项目配置
├── database/              # 数据库模块
│   ├── __init__.py
│   ├── db_manager.py     # DuckDB管理器
│   └── schema.py         # 表结构定义
├── data/                  # 数据模块
│   ├── __init__.py
│   ├── fetchers/         # 数据获取
│   │   └── stock_fetcher.py
│   └── updaters/         # 数据更新
│       └── data_updater.py
├── strategies/            # 策略模块
│   ├── __init__.py
│   ├── base/             # 策略基类
│   │   ├── base_strategy.py
│   │   └── multi_factor_strategy.py
│   ├── impl/             # 策略实现
│   └── config/           # 策略配置
├── backtest/             # 回测模块
│   ├── __init__.py
│   ├── engine.py        # 回测引擎
│   ├── analyzer.py      # 绩效分析
│   └── multi_dimension.py # 多维度分析
├── tools/                # 工具模块
│   ├── __init__.py
│   ├── indicators/      # 技术指标
│   │   └── technical.py
│   ├── analysis/        # 分析工具
│   └── visualization/   # 可视化
├── debug/               # AI调试层
│   ├── agent/          # OpenClaw集成
│   ├── logs/           # 调试日志
│   └── reports/        # 分析报告
├── origintxt/          # 策略文本
├── scripts/            # 脚本工具
│   └── init_project.py # 项目初始化
├── tests/              # 测试套件
├── data/               # 数据目录
│   ├── Astock3.duckdb       # DuckDB数据库
│   ├── raw/           # 原始数据
│   └── processed/     # 处理后数据
├── results/            # 回测结果
└── logs/               # 日志文件
    """
    
    print(structure)


def main():
    """主函数"""
    print("\n" + "="*60)
    print("  量化交易系统 - 项目初始化")
    print("="*60)
    
    # 1. 检查依赖
    if not check_dependencies():
        print("\n依赖检查失败，请安装缺失的包")
        return
    
    # 2. 创建目录结构
    create_directory_structure()
    
    # 3. 初始化数据库
    if not init_database():
        print("\n数据库初始化失败")
        return
    
    # 4. 测试数据连接
    if not test_data_connection():
        print("\n数据连接测试失败")
        return
    
    # 5. 下载股票列表
    download_stock_list()
    
    # 6. 打印项目结构
    print_project_structure()
    
    print("\n" + "="*60)
    print("  项目初始化完成！")
    print("="*60)
    print("\n下一步操作:")
    print("  1. 运行数据更新: python -m data.updaters.data_updater")
    print("  2. 创建策略: 在 strategies/impl/ 目录下创建策略文件")
    print("  3. 运行回测: 使用 backtest/engine.py 进行回测")
    print("\n")


if __name__ == '__main__':
    main()
