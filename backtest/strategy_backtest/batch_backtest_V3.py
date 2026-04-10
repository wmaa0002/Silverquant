"""
批量回测脚本 V2

支持策略注册表，自动适配不同策略的参数需求。

策略注册表格式:
    '策略文件名': {
        'threshold_required': True/False,  # 是否需要threshold参数
        'min_data_days': 60,               # 最小数据天数
    }

使用示例:
    python batch_backtest_V2.py -l 100 --start 20250101 --end 20251231 --strategy 天宫暴力K策略V1
"""

import sys
import argparse
import os
import logging
from pathlib import Path
import inspect

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import duckdb
from datetime import datetime
from backtest.engine import BacktestEngine
from scripts.log_utils import setup_logger


ASTOCK3_DB_PATH = project_root / 'data' / 'Astock3.duckdb'


# ============== 策略注册表 ==============
# 新增策略时，只需在这里添加配置，无需修改核心代码
STRATEGY_CONFIG = {
    # 格式: '策略文件名': {配置}
    
    # 天宫B1策略
    '天宫B1策略v1': {
        'threshold_required': True,
        'min_data_days': 60,
    },
    '天宫B1策略v2.1': {
        'threshold_required': True,
        'min_data_days': 60,
    },
    
    # 天宫B2策略
    '天宫B2策略': {
        'threshold_required': True,
        'min_data_days': 60,
    },
    '天宫B2策略v2': {
        'threshold_required': True,
        'min_data_days': 60,
    },
    
    # 暴力K策略 - 不需要threshold，最小数据天数30天
    '天宫暴力K策略V1': {
        'threshold_required': False,
        'min_data_days': 30,
},
    
    # 暴力K+B2策略 - 需要threshold，最小数据天数60天
    '天宫暴力K+B2策略V1': {
        'threshold_required': True,
        'min_data_days': 60,
    },
    
    # 地量策略 - 不需要threshold，最小数据天数50天
    '天宫地量策略V1': {
        'threshold_required': False,
        'min_data_days': 50,
},
    
    # 沙尘暴策略 - 不需要threshold，最小数据天数60天
    '天宫沙尘暴策略V1': {
    },
    
    # 天宫单针30策略 - 不需要threshold，最小数据天数60天
    '天宫单针30策略V1': {
        'threshold_required': False,
        'min_data_days': 60,
    },
    
    # 未来新增策略只需添加配置...
    # '新策略名': {
    #     'threshold_required': True/False,
    #     'min_data_days': 60,
    # },
}


def get_stock_list_from_db(limit: int = None, industry: str = None, 
                           market_cap_min: float = None, market_cap_max: float = None) -> pd.DataFrame:
    """从数据库获取股票列表（从 dwd_stock_info 读取）
    
    注意: market_cap 字段在 dwd_stock_info 中不存在，
          market_cap_min/max 筛选将被忽略（与旧表行为一致，旧表此字段99.9%为空）
    """
    conn = duckdb.connect(str(ASTOCK3_DB_PATH))
    
    # 字段映射: code←symbol, market_cap 字段已移除
    query = "SELECT symbol AS code, name, industry FROM dwd_stock_info WHERE list_status = 'L'"
    
    if industry:
        query += f" AND industry = '{industry}'"
    # market_cap 筛选: dwd_stock_info 无此字段，跳过（与旧表一致，旧表此字段99.9%为空）
    
    if limit:
        query += f" LIMIT {limit}"
    
    df = conn.execute(query).df()
    conn.close()
    return df


def get_data_from_astock3(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取单个股票数据"""
    start_date_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    
    conn = duckdb.connect(str(ASTOCK3_DB_PATH))
    df = conn.execute(f"""
        SELECT trade_date, ts_code, open, high, low, close, vol, amount
        FROM dwd_daily_price 
        WHERE ts_code = '{stock_code}' 
        AND trade_date >= '{start_date_fmt}' 
        AND trade_date <= '{end_date_fmt}'
        ORDER BY trade_date
    """).fetchdf()
    conn.close()
    
    if df is not None and len(df) > 0:
        df = df.rename(columns={
            'trade_date': 'date',
            'ts_code': 'code',
            'vol': 'volume'
        })
    
    if df is None or len(df) == 0:
        return None
    
    df = df.rename(columns={
        'date': 'datetime',
        'amount': 'openinterest'
    })
    
    return df


def load_strategy_class(strategy_name: str):
    """加载策略类"""
    strategy_file = project_root / 'strategies' / f'{strategy_name}.py'
    
    with open(strategy_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    namespace = {}
    exec(content, namespace)
    
    for name in namespace:
        if name.endswith('Strategy') and name != 'BaseStrategy':
            return namespace[name]
    
    raise ValueError(f"未找到策略类 in {strategy_file}")


def get_strategy_config(strategy_file: str) -> dict:
    """获取策略配置，如果未注册则使用默认值"""
    if strategy_file in STRATEGY_CONFIG:
        return STRATEGY_CONFIG[strategy_file]
    else:
        logging.warning(f"策略 '{strategy_file}' 未在注册表中，使用默认配置")
        return {
            'threshold_required': True,  # 默认需要threshold
            'min_data_days': 60,          # 默认60天
        }


def add_strategy_to_engine(engine, strategy_class, threshold: float, strategy_file: str):
    """
    自动检测策略需要的参数并添加策略
    
    根据策略注册表或运行时检测，自动判断需要哪些参数
    """
    # 方法1: 先尝试从注册表获取配置
    config = get_strategy_config(strategy_file)
    
    if not config['threshold_required']:
        # 不需要threshold的策略（如BLK）
        engine.add_strategy(strategy_class)
        return
    
    # 方法2: 运行时检测策略构造参数
    sig = inspect.signature(strategy_class.__init__)
    params = sig.parameters
    
    kwargs = {}
    if 'b1_threshold' in params:
        kwargs['b1_threshold'] = threshold
    elif 'b2_threshold' in params:
        kwargs['b2_threshold'] = threshold
    
    engine.add_strategy(strategy_class, **kwargs)


def run_single_backtest(stock_code: str, stock_name: str, start_date: str, end_date: str,
                        strategy_file: str, threshold: float, initial_cash: float,
                        save_to_db: bool = True) -> dict:
    """运行单个股票回测"""
    from datetime import date
    
    from_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    to_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    
    strategy_class = load_strategy_class(strategy_file)
    
    df = get_data_from_astock3(stock_code, start_date, end_date)
    
    if df is None or len(df) == 0:
        return {
            'code': stock_code,
            'name': stock_name,
            'status': 'no_data',
            'error': '未找到数据'
        }
    
    # 使用策略配置中的最小数据天数
    config = get_strategy_config(strategy_file)
    min_days = config['min_data_days']
    
    if len(df) < min_days:
        return {
            'code': stock_code,
            'name': stock_name,
            'status': 'insufficient_data',
            'error': f'数据不足({len(df)}条，需要{min_days}条)'
        }
    
    try:
        engine = BacktestEngine(
            initial_cash=initial_cash,
            commission=0.0003,
            stamp_duty=0.001,
            slip_page=0.001
        )
        
        engine.add_data(
            df, 
            name=stock_code,
            fromdate=from_date,
            todate=to_date
        )
        
        # 使用新的自动添加策略方法
        add_strategy_to_engine(engine, strategy_class, threshold, strategy_file)
        
        result = engine.run(
            strategy_name=strategy_class.__name__,
            save_results=save_to_db
        )
        
        metrics = result.get('metrics', {})
        
        return {
            'code': stock_code,
            'name': stock_name,
            'status': 'success',
            'run_id': engine.run_id,
            'initial_cash': initial_cash,
            'final_value': result.get('final_value', 0),
            'total_return': metrics.get('total_return', 0),
            'annualized_return': metrics.get('annualized_return', 0),
            'max_drawdown': metrics.get('max_drawdown', 0),
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'win_rate': metrics.get('win_rate', 0),
            'total_trades': metrics.get('total_trades', 0),
            'trade_records': result.get('trade_records', []),
        }
        
    except Exception as e:
        import traceback
        return {
            'code': stock_code,
            'name': stock_name,
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }


def run_batch_backtest(stocks: list, start_date: str, end_date: str,
                        strategy_file: str, threshold: float, initial_cash: float = 100000,
                        save_to_db: bool = True, report_dir: str = None):
    batch_log_dir = project_root / 'results' / f"batch_{strategy_file}_{start_date}_{end_date}"
    batch_log_dir.mkdir(parents=True, exist_ok=True)
    
    logger = setup_logger(f'batch_{strategy_file}', 'backtest')
    logger.info(f"批量回测开始")
    logger.info(f"策略: {strategy_file}")
    logger.info(f"期间: {start_date} - {end_date}")
    logger.info(f"初始资金: {initial_cash:,.0f}")
    logger.info(f"股票数量: {len(stocks)}")
    
    config = get_strategy_config(strategy_file)
    logger.info(f"策略配置: threshold_required={config['threshold_required']}, min_data_days={config['min_data_days']}")
    
    results = []
    success_count = 0
    fail_count = 0
    no_data_count = 0
    
    for i, stock in enumerate(stocks, 1):
        code = stock.get('code', '')
        name = stock.get('name', '')
        
        logger.info(f"[{i}/{len(stocks)}] {code} {name}...")
        
        result = run_single_backtest(
            code, name, start_date, end_date,
            strategy_file, threshold, initial_cash, save_to_db
        )
        
        if result['status'] == 'success':
            success_count += 1
            logger.info(f"✓ {code} 收益率={result['total_return']*100:.2f}%")
        elif result['status'] == 'no_data':
            no_data_count += 1
            logger.info(f"✗ {code} 无数据")
        else:
            fail_count += 1
            logger.warning(f"✗ {code} {result.get('error', '未知错误')}")
        
        results.append(result)
    
    logger.info(f"回测完成 - 总计:{len(stocks)} 成功:{success_count} 无数据:{no_data_count} 失败:{fail_count}")
    
    success_results = [r for r in results if r.get('status') == 'success']
    if success_results:
        avg_return = sum(r['total_return'] for r in success_results) / len(success_results)
        avg_trades = sum(r['total_trades'] for r in success_results) / len(success_results)
        avg_winrate = sum(r['win_rate'] for r in success_results) / len(success_results)
        
        logger.info(f"成功案例统计: 平均收益率={avg_return*100:.2f}%, 平均交易次数={avg_trades:.1f}, 平均胜率={avg_winrate*100:.1f}%")
        
        top5 = sorted(success_results, key=lambda x: x['total_return'], reverse=True)[:5]
        logger.info(f"收益Top5:")
        for r in top5:
            logger.info(f"  {r['code']}: {r['total_return']*100:.2f}%")
    
    results_df = pd.DataFrame(results)
    csv_path = batch_log_dir / f'{strategy_file}_batch_results.csv'
    results_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    logger.info(f"结果已保存到: {csv_path}")
    results_df = pd.DataFrame(results)
    
    return results_df


def main():
    parser = argparse.ArgumentParser(description='批量股票策略回测 V2')
    
    parser.add_argument('--stocks', '-s', nargs='+', default=None, 
                       help='股票代码列表，如: 300349 300486')
    parser.add_argument('--stock-file', '-f', default=None,
                       help='股票代码文件（每行一个代码）')
    parser.add_argument('--stock', '-S', default=None, help='股票代码 (单股票模式)'),
    parser.add_argument('--limit', '-l', type=int, default=None,
                       help='从数据库获取的股票数量')
    parser.add_argument('--industry', '-i', type=str, default=None,
                       help='行业过滤')
    parser.add_argument('--start', default='20250101', help='开始日期 YYYYMMDD')
    parser.add_argument('--end', default='20251231', help='结束日期 YYYYMMDD')
    parser.add_argument('--cash', type=float, default=100000, help='初始资金')
    parser.add_argument('--strategy', default='天宫B1策略v1', help='策略文件名')
    parser.add_argument('--threshold', type=float, default=8.0, help='策略阈值')
    parser.add_argument('--no-save', action='store_true', help='不保存到数据库')
    parser.add_argument('--output', '-o', default=None, help='结果输出目录')
    
    args = parser.parse_args()
    
    # 单股票模式 (调用run_backtest)
    if args.stock:
        from run_backtest import run_backtest as run_single
        run_single(args.stock, args.start, args.end, args.cash, args.strategy, args.threshold, not args.no_save)
        return
    
    stocks = None
    
    if args.stocks:
        stocks = [{'code': code, 'name': ''} for code in args.stocks]
    elif args.stock_file:
        with open(args.stock_file, 'r') as f:
            codes = [line.strip() for line in f if line.strip()]
        stocks = [{'code': code, 'name': ''} for code in codes]
    elif args.limit or args.industry:
        stock_df = get_stock_list_from_db(
            limit=args.limit, 
            industry=args.industry
        )
        stocks = stock_df.to_dict('records')
    
    run_batch_backtest(
        stocks=stocks,
        start_date=args.start,
        end_date=args.end,
        strategy_file=args.strategy,
        threshold=args.threshold,
        initial_cash=args.cash,
        save_to_db=not args.no_save,
        report_dir=args.output
    )


if __name__ == '__main__':
    main()
