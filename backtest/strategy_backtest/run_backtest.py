import sys
import argparse
import os
from pathlib import Path
from datetime import datetime
import inspect

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import duckdb

from backtest.engine import BacktestEngine
from scripts.log_utils import setup_logger


def get_data_from_astock3(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    db_path = project_root / 'data' / 'Astock3.duckdb'
    
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")
    
    start_date_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    
    db = duckdb.connect(str(db_path))
    df = db.execute(f"""
        SELECT trade_date, ts_code, open, high, low, close, vol, amount
        FROM dwd_daily_price 
        WHERE ts_code = '{stock_code}' 
        AND trade_date >= '{start_date_fmt}' 
        AND trade_date <= '{end_date_fmt}'
        ORDER BY trade_date
    """).fetchdf()
    db.close()
    
    if df is not None and len(df) > 0:
        df = df.rename(columns={
            'trade_date': 'date',
            'ts_code': 'code',
            'vol': 'volume'
        })
    
    if df is None or len(df) == 0:
        raise ValueError(f"未在数据库中找到 {stock_code} 的数据")
    
    df = df.rename(columns={
        'date': 'datetime',
        'amount': 'openinterest'
    })
    
    return df


def load_strategy_class(strategy_name: str = '天宫B1策略v1'):
    strategy_file = project_root / 'strategies' / f'{strategy_name}.py'
    
    with open(strategy_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    namespace = {}
    exec(content, namespace)
    
    # 优先查找具体的策略类（排除BaseStrategy）
    for name in namespace:
        if name.endswith('Strategy') and name != 'BaseStrategy':
            return namespace[name]
    
    raise ValueError(f"未找到策略类 in {strategy_file}")


def run_backtest(
    stock_code: str = "300486",
    start_date: str = "20240101",
    end_date: str = "20241231",
    initial_cash: float = 100000.0,
    strategy_file: str = "天宫B1策略v1",
    threshold: float = 8.0,
    save_to_db: bool = True
):
    from_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
    to_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
    
    strategy_class = load_strategy_class(strategy_file)
    
    # 创建结果目录（先创建，后续日志会写入此处）
    # timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    report_dir = project_root / 'results' / f"backtest_{stock_code}_{strategy_file}_{start_date}_{end_date}"
    os.makedirs(report_dir, exist_ok=True)
    
    logger = setup_logger(f'backtest_{strategy_file}', 'backtest')
    logger.info(f"=== 回测配置 ===")
    logger.info(f"股票代码: {stock_code}")
    logger.info(f"回测期间: {from_date} 至 {to_date}")
    logger.info(f"初始资金: {initial_cash:,.2f}")
    logger.info(f"策略类: {strategy_class.__name__}")
    logger.info(f"策略文件: {strategy_file}.py")
    logger.info(f"数据源: Astock3.duckdb")
    logger.info(f"策略参数: threshold={threshold}")
    
    df = get_data_from_astock3(stock_code, start_date, end_date)
    logger.info(f"从Astock3.duckdb获取到 {len(df)} 条数据")
    logger.info(f"数据起始日期: {df['datetime'].iloc[0]}")
    logger.info(f"数据结束日期: {df['datetime'].iloc[-1]}")
    
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
    
    sig = inspect.signature(strategy_class.__init__)
    params = sig.parameters
    
    if 'b1_threshold' in params:
        engine.add_strategy(strategy_class, b1_threshold=threshold)
    elif 'b2_threshold' in params:
        engine.add_strategy(strategy_class, b2_threshold=threshold)
    else:
        engine.add_strategy(strategy_class)
    
    result = engine.run(
        strategy_name=strategy_class.__name__,
        save_results=save_to_db
    )
    
    if save_to_db and engine.run_id:
        logger.info(f"生成可视化报告...")
    
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'charts', 
        str(project_root / 'tools/visualization/charts.py')
    )
    charts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(charts)
    ChartPlotter = charts.ChartPlotter
    plotter = ChartPlotter(show=False)
    
    plotter.plot_backtest_performance(engine.run_id, save_path=f"{report_dir}/performance.png")
    plotter.plot_backtest_equity_curve(engine.run_id, save_path=f"{report_dir}/equity_curve.png")
    plotter.plot_trade_statistics(engine.run_id, save_path=f"{report_dir}/trade_statistics.png")
    
    trades = plotter.load_backtest_trades(engine.run_id)
    if not trades.empty:
        codes = trades['code'].dropna().unique()
        for code in codes:
            if code:
                plotter.plot_trades_on_price(engine.run_id, code=code, save_path=f"{report_dir}/trades_{code}.png")
    
    logger.info(f"可视化报告已保存到: {report_dir}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='股票策略回测')
    parser.add_argument('--stock', '-s', default='300486', help='股票代码')
    parser.add_argument('--start', default='20240101', help='开始日期 YYYYMMDD')
    parser.add_argument('--end', default='20241231', help='结束日期 YYYYMMDD')
    parser.add_argument('--cash', type=float, default=100000, help='初始资金')
    parser.add_argument('--strategy', default='天宫B1策略backet', help='策略文件名')
    parser.add_argument('--threshold', type=float, default=8.0, help='策略阈值')
    parser.add_argument('--no-save', action='store_true', help='不保存到数据库')
    
    args = parser.parse_args()
    
    run_backtest(
        stock_code=args.stock,
        start_date=args.start,
        end_date=args.end,
        initial_cash=args.cash,
        strategy_file=args.strategy,
        threshold=args.threshold,
        save_to_db=not args.no_save
    )


if __name__ == "__main__":
    main()
