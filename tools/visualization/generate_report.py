#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回测报告生成脚本

用法:
    python generate_report.py              # 使用最新的回测
    python generate_report.py --latest     # 使用最新的回测
    python generate_report.py --run-id ad006508  # 使用指定回测
    python generate_report.py --all         # 生成所有回测的报告
    python generate_report.py -l            # 列出所有可用的回测
"""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import importlib.util
spec = importlib.util.spec_from_file_location(
    'charts', 
    str(PROJECT_ROOT / 'tools/visualization/charts.py')
)
charts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(charts)

ChartPlotter = charts.ChartPlotter


def list_runs(plotter: ChartPlotter, limit: int = 20):
    """列出所有可用的回测"""
    runs = plotter.load_backtest_runs(limit=limit)
    
    if runs.empty:
        print("没有找到回测记录")
        return []
    
    print("\n" + "="*70)
    print("可用的回测记录")
    print("="*70)
    print(f"{'序号':<4} {'run_id':<12} {'策略':<25} {'日期':<12} {'状态':<10}")
    print("-"*70)
    
    for i, row in runs.iterrows():
        run_id = row['run_id']
        strategy = row.get('strategy_name', 'N/A')[:22]
        date = str(row.get('start_date', 'N/A'))
        status = row.get('status', 'N/A') or 'running'
        
        # 检查是否有交易数据
        trades = plotter.load_backtest_trades(run_id)
        trade_count = len(trades)
        
        print(f"{i+1:<4} {run_id:<12} {strategy:<25} {date:<12} {status:<8} [{trade_count}笔]")
    
    print("="*70)
    return runs


def generate_report(
    plotter: ChartPlotter, 
    run_id: str, 
    save_dir: str = None,
    show: bool = False
):
    """生成单个回测的报告"""
    # 获取汇总信息
    summary = plotter.load_backtest_summary_by_run_id(run_id)
    
    if not summary:
        print(f"错误: 未找到回测 {run_id}")
        return False
    
    strategy = summary.get('strategy_name', 'Unknown')
    start_date = summary.get('start_date', 'N/A')
    
    # 创建保存目录
    if save_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        save_dir = str(PROJECT_ROOT / 'results' / f"{run_id}_{timestamp}")
    
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"生成报告: {run_id}")
    print(f"策略: {strategy}")
    print(f"日期: {start_date}")
    print(f"保存目录: {save_dir}")
    print("="*60)
    
    # 1. 绩效指标
    print("[1/4] 绘制绩效指标...")
    plotter.plot_backtest_performance(
        run_id, 
        save_path=f"{save_dir}/performance.png"
    )
    
    # 2. 权益曲线
    print("[2/4] 绘制权益曲线...")
    plotter.plot_backtest_equity_curve(
        run_id,
        save_path=f"{save_dir}/equity_curve.png"
    )
    
    # 3. 交易统计
    print("[3/4] 绘制交易统计...")
    plotter.plot_trade_statistics(
        run_id,
        save_path=f"{save_dir}/trade_statistics.png"
    )
    
    # 4. 交易记录详情
    trades = plotter.load_backtest_trades(run_id)
    if not trades.empty:
        print("[4/4] 绘制交易记录...")
        # 按股票分组绘制
        codes = trades['code'].dropna().unique()
        for code in codes:
            if code:
                plotter.plot_trades_on_price(
                    run_id,
                    code=code,
                    save_path=f"{save_dir}/trades_{code}.png"
                )
    else:
        print("[4/4] 无交易记录，跳过")
    
    print(f"\n✓ 报告生成完成: {save_dir}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='回测报告生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python generate_report.py                    # 使用最新回测
  python generate_report.py --latest            # 使用最新回测
  python generate_report.py --run-id ad006508   # 使用指定回测
  python generate_report.py --all                # 生成所有回测报告
  python generate_report.py -l                  # 列出所有回测
  python generate_report.py -o /tmp/reports     # 指定输出目录
        """
    )
    
    parser.add_argument(
        '-l', '--list', 
        action='store_true',
        help='列出所有可用的回测记录'
    )
    
    parser.add_argument(
        '--run-id', '-r',
        type=str,
        default=None,
        help='指定回测ID'
    )
    
    parser.add_argument(
        '--latest', '-L',
        action='store_true',
        help='使用最新的回测'
    )
    
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='生成所有回测的报告'
    )
    
    parser.add_argument(
        '--batch', '-b',
        type=str,
        default=None,
        help='批量模式: 指定CSV文件路径生成批量汇总报告'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='输出目录 (默认: ./results/<run_id>)'
    )
    
    parser.add_argument(
        '--show', '-s',
        action='store_true',
        help='显示图表 (默认只保存)'
    )
    
    args = parser.parse_args()
    
    # 初始化
    plotter = ChartPlotter(show=args.show)
    
    # 列出回测
    if args.list:
        list_runs(plotter)
        return
    
    # 批量模式
    if args.batch:
        import pandas as pd
        csv_path = args.batch
        if not os.path.exists(csv_path):
            print(f"错误: 文件不存在 {csv_path}")
            return
        
        results_df = pd.read_csv(csv_path)
        
        # 设置默认输出目录
        if args.output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            args.output = str(PROJECT_ROOT / 'results' / f"batch_{timestamp}")
        
        os.makedirs(args.output, exist_ok=True)
        
        print(f"生成批量汇总报告: {args.output}")
        plotter.plot_batch_summary(results_df, save_dir=args.output)
        return
    
    # 获取回测列表
    runs = plotter.load_backtest_runs(limit=50)
    
    if runs.empty:
        print("错误: 没有找到回测记录")
        return
    
    # 确定要处理的run_id列表
    target_runs = []
    
    if args.all:
        # 所有回测
        target_runs = runs['run_id'].tolist()
        print(f"将生成 {len(target_runs)} 个回测的报告")
        
    elif args.run_id:
        # 指定回测 - 先尝试精确匹配，不限制数量
        runs_all = plotter.load_backtest_runs(limit=500)
        if args.run_id in runs_all['run_id'].values:
            target_runs = [args.run_id]
        else:
            print(f"错误: 未找到回测 {args.run_id}")
            return
    
    elif args.latest or args.run_id is None:
        # 最新回测
        target_runs = [runs.iloc[0]['run_id']]
        print(f"使用最新回测: {target_runs[0]}")
    
    else:
        # 交互式选择
        runs_with_data = list_runs(plotter)
        
        print("\n请选择回测:")
        print("  输入序号 (1-N): 生成单个报告")
        print("  输入 'a': 生成所有报告")
        print("  输入 'l': 重新列出")
        print("  输入 'q': 退出")
        
        while True:
            choice = input("\n请选择: ").strip().lower()
            
            if choice == 'q':
                print("退出")
                return
            elif choice == 'l':
                list_runs(plotter)
            elif choice == 'a':
                target_runs = runs_with_data['run_id'].tolist()
                break
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(runs_with_data):
                        target_runs = [runs_with_data.iloc[idx]['run_id']]
                        break
                    else:
                        print("序号超出范围")
                except ValueError:
                    print("无效输入")
    
    # 生成报告
    print(f"\n开始生成 {len(target_runs)} 个报告...\n")
    
    success_count = 0
    for i, run_id in enumerate(target_runs, 1):
        print(f"\n[{i}/{len(target_runs)}] 处理 {run_id}")
        if generate_report(plotter, run_id, args.output, args.show):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"完成! 成功生成 {success_count}/{len(target_runs)} 个报告")
    print("="*60)


if __name__ == '__main__':
    main()
