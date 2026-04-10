"""
多Agent系统测试流程
测试日期: 2026-03-27
测试目标: daily_signals表中所有出现买入信号的股票
"""
import sys
import os
import time
import pandas as pd
import duckdb
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_integration.api.analyzer import analyze_stock


def get_buy_signals_stocks(date: str) -> pd.DataFrame:
    """获取指定日期有买入信号的股票"""
    db_path = Path(__file__).parent.parent.parent / 'data' / 'Astock3.duckdb'
    
    query = f"""
    SELECT 
        code, 
        name, 
        signal_buy_b1, 
        signal_buy_b2, 
        signal_buy_blk, 
        signal_buy_dl, 
        signal_buy_dz30, 
        signal_buy_scb, 
        signal_buy_blkB2 
    FROM daily_signals 
    WHERE date = '{date}' 
    AND (
        signal_buy_b1 = True 
        OR signal_buy_b2 = True 
        OR signal_buy_blk = True 
        OR signal_buy_dl = True 
        OR signal_buy_dz30 = True 
        OR signal_buy_scb = True 
        OR signal_buy_blkB2 = True
    )
    """
    
    try:
        db = duckdb.connect(str(db_path), read_only=True)
        df = db.execute(query).df()
        db.close()
        return df
    except Exception as e:
        print(f"查询失败: {e}")
        return pd.DataFrame()


def run_ai_analysis_test(stocks_df: pd.DataFrame, trade_date: str) -> pd.DataFrame:
    """运行AI分析测试"""
    results = []
    
    for idx, row in stocks_df.iterrows():
        code = row['code']
        name = row['name']
        
        signals = []
        signal_cols = ['signal_buy_b1', 'signal_buy_b2', 'signal_buy_blk', 'signal_buy_dl', 'signal_buy_dz30', 'signal_buy_scb', 'signal_buy_blkB2']
        for col in signal_cols:
            if row.get(col, False):
                signals.append(col.replace('signal_buy_', '').upper())
        
        signal_sources = '+'.join(signals) if signals else 'NONE'
        
        print(f"[{idx+1}/{len(stocks_df)}] 分析 {code} {name}...", end=" ")
        
        start_time = time.time()
        try:
            result = analyze_stock(code, trade_date, include_memory=False)
            duration = time.time() - start_time
            
            risk_level = 'UNKNOWN'
            position_size = 0.0
            try:
                risk_level = result.get('debate_round', {}).get('final_risk_level', 'UNKNOWN')
                position_size = result.get('trading_signal', {}).get('position_size', 0)
            except:
                pass
            
            results.append({
                'stock_code': code,
                'stock_name': name,
                'ai_decision': result.get('final_decision', 'ERROR'),
                'ai_confidence': result.get('confidence', 0),
                'risk_level': risk_level,
                'position_size': position_size,
                'duration_seconds': round(duration, 2),
                'signal_sources': signal_sources,
                'success': result.get('success', False),
                'error': result.get('error', '')
            })
            print(f"✓ {result.get('final_decision', 'ERROR')} ({duration:.1f}s)")
        except Exception as e:
            duration = time.time() - start_time
            results.append({
                'stock_code': code,
                'stock_name': name,
                'ai_decision': 'ERROR',
                'ai_confidence': 0,
                'risk_level': 'UNKNOWN',
                'position_size': 0,
                'duration_seconds': round(duration, 2),
                'signal_sources': signal_sources,
                'success': False,
                'error': str(e)
            })
            print(f"✗ ERROR ({duration:.1f}s)")
    
    return pd.DataFrame(results)


def main():
    TEST_DATE = '2026-03-27'
    TRADE_DATE = '2026-03-28'
    
    print("=" * 60)
    print("多Agent系统测试")
    print(f"信号日期: {TEST_DATE}")
    print(f"分析日期: {TRADE_DATE}")
    print("=" * 60)
    
    print("\n[Step 1] 查询daily_signals买入信号...")
    stocks = get_buy_signals_stocks(TEST_DATE)
    print(f"找到 {len(stocks)} 只股票有买入信号")
    
    if len(stocks) == 0:
        print("没有找到符合条件的股票，退出")
        return
    
    print("\n股票列表:")
    print(stocks[['code', 'name']].to_string(index=False))
    
    print("\n[Step 2] 运行AI分析...")
    results = run_ai_analysis_test(stocks, TRADE_DATE)
    
    print("\n[Step 3] 保存结果...")
    output_dir = Path(__file__).parent.parent / 'test_results'
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f'{TEST_DATE}_test_results.csv'
    results.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"结果已保存到: {output_file}")
    
    print("\n" + "=" * 60)
    print("测试结果统计")
    print("=" * 60)
    
    success_results = results[results['success'] == True]
    
    print(f"总股票数: {len(results)}")
    print(f"成功分析: {len(success_results)}")
    print(f"失败: {len(results) - len(success_results)}")
    
    if len(success_results) > 0:
        print(f"\n决策分布:")
        decision_counts = success_results['ai_decision'].value_counts()
        for decision, count in decision_counts.items():
            pct = count / len(success_results) * 100
            print(f"  {decision}: {count} ({pct:.1f}%)")
        
        print(f"\n平均置信度: {success_results['ai_confidence'].mean():.2f}")
        print(f"平均耗时: {success_results['duration_seconds'].mean():.1f}秒")
        print(f"最快: {success_results['duration_seconds'].min():.1f}秒")
        print(f"最慢: {success_results['duration_seconds'].max():.1f}秒")
    
    print("\n详细结果:")
    print("-" * 60)
    print(results.to_string(index=False))


if __name__ == '__main__':
    main()