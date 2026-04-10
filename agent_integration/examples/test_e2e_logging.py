"""
多Agent系统端到端测试脚本
========================

功能:
1. 从daily_signals表查询2026-03-27所有买入信号股票
2. 对每只股票运行完整的多Agent分析流程
3. 记录每只股票的分析耗时
4. 完整的日志系统记录所有运行过程

使用方式:
    python agent_integration/examples/test_e2e_logging.py
"""

import sys
import os
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import duckdb
import pandas as pd

from agent_integration.api.analyzer import analyze_stock


class AnalysisLogger:
    """分析日志记录器"""
    
    def __init__(self, log_dir: str = None, run_id: str = None):
        """初始化日志记录器
        
        Args:
            log_dir: 日志目录
            run_id: 运行ID
        """
        if run_id is None:
            run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.run_id = run_id
        
        if log_dir is None:
            log_dir = Path(__file__).parent.parent.parent / 'logs' / 'e2e_test'
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志文件路径
        self.main_log_file = self.log_dir / f'{run_id}_main.log'
        self.detail_log_file = self.log_dir / f'{run_id}_detail.log'
        self.error_log_file = self.log_dir / f'{run_id}_error.log'
        self.result_json_file = self.log_dir / f'{run_id}_results.json'
        
        # 设置主日志器
        self.logger = logging.getLogger(f'e2e_test_{run_id}')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers = []
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器
        file_handler = logging.FileHandler(self.main_log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 错误日志处理器
        error_handler = logging.FileHandler(self.error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
        
        # 详细日志处理器
        detail_handler = logging.FileHandler(self.detail_log_file, encoding='utf-8')
        detail_handler.setLevel(logging.DEBUG)
        detail_handler.setFormatter(file_formatter)
        self.logger.addHandler(detail_handler)
        
        # 运行结果存储
        self.results: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.stage_times: Dict[str, float] = {}
        
        self.logger.info(f"日志系统初始化完成, RunID: {run_id}")
        self.logger.info(f"日志目录: {self.log_dir}")
    
    def log_stage_start(self, stage: str, info: str = ""):
        """记录阶段开始"""
        self.logger.info(f"[{stage}] 开始 {info}")
        self.stage_times[f"{stage}_start"] = time.time()
    
    def log_stage_end(self, stage: str, duration: float = None):
        """记录阶段结束"""
        if duration is None and f"{stage}_start" in self.stage_times:
            duration = time.time() - self.stage_times[f"{stage}_start"]
        self.logger.info(f"[{stage}] 完成, 耗时: {duration:.2f}秒" if duration else f"[{stage}] 完成")
    
    def log_info(self, message: str, stock_code: str = None):
        """记录一般信息"""
        prefix = f"[{stock_code}]" if stock_code else ""
        self.logger.info(f"{prefix} {message}")
    
    def log_detail(self, message: str, stock_code: str = None):
        """记录详细信息"""
        prefix = f"[{stock_code}]" if stock_code else ""
        self.logger.debug(f"{prefix} {message}")
    
    def log_error(self, message: str, stock_code: str = None, error: Exception = None):
        """记录错误"""
        prefix = f"[{stock_code}]" if stock_code else ""
        if error:
            self.logger.error(f"{prefix} {message}: {str(error)}")
        else:
            self.logger.error(f"{prefix} {message}")
    
    def log_warning(self, message: str, stock_code: str = None):
        """记录警告"""
        prefix = f"[{stock_code}]" if stock_code else ""
        self.logger.warning(f"{prefix} {message}")
    
    def log_result(self, result: Dict[str, Any], duration: float):
        """记录单只股票分析结果"""
        self.results.append({
            'stock_code': result.get('stock_code'),
            'stock_name': result.get('stock_name'),
            'ai_decision': result.get('ai_decision'),
            'ai_confidence': result.get('ai_confidence'),
            'risk_level': result.get('risk_level'),
            'position_size': result.get('position_size'),
            'duration_seconds': duration,
            'signal_sources': result.get('signal_sources'),
            'success': result.get('success', False),
            'error': result.get('error', '')
        })
    
    def log_error_result(self, stock_code: str, stock_name: str, error: str, duration: float):
        """记录错误结果"""
        self.errors.append({
            'stock_code': stock_code,
            'stock_name': stock_name,
            'error': error,
            'duration': duration
        })
    
    def save_results(self):
        """保存结果到JSON"""
        output = {
            'run_id': self.run_id,
            'timestamp': datetime.now().isoformat(),
            'total_stocks': len(self.results),
            'success_count': sum(1 for r in self.results if r['success']),
            'error_count': len(self.errors),
            'results': self.results,
            'errors': self.errors,
            'stage_times': {k: v for k, v in self.stage_times.items() if '_start' not in k}
        }
        
        with open(self.result_json_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"结果已保存到: {self.result_json_file}")
    
    def print_summary(self):
        """打印汇总"""
        print("\n" + "=" * 70)
        print("测试结果汇总")
        print("=" * 70)
        
        success_results = [r for r in self.results if r['success']]
        
        print(f"\n总股票数: {len(self.results)}")
        print(f"成功分析: {len(success_results)}")
        print(f"失败: {len(self.results) - len(success_results)}")
        
        if success_results:
            print(f"\n决策分布:")
            decision_counts = {}
            for r in success_results:
                d = r['ai_decision']
                decision_counts[d] = decision_counts.get(d, 0) + 1
            
            for decision, count in sorted(decision_counts.items()):
                pct = count / len(success_results) * 100
                print(f"  {decision}: {count} ({pct:.1f}%)")
            
            print(f"\n性能指标:")
            durations = [r['duration_seconds'] for r in success_results]
            confidences = [r['ai_confidence'] for r in success_results]
            
            print(f"  平均置信度: {sum(confidences)/len(confidences):.2f}")
            print(f"  平均耗时: {sum(durations)/len(durations):.1f}秒")
            print(f"  最快: {min(durations):.1f}秒")
            print(f"  最慢: {max(durations):.1f}秒")
            print(f"  总耗时: {sum(durations):.1f}秒 ({sum(durations)/60:.1f}分钟)")
        
        if self.errors:
            print(f"\n遇到的问题 ({len(self.errors)}次):")
            error_types = {}
            for err in self.errors:
                err_key = err['error'][:60] if err['error'] else 'Unknown'
                if err_key not in error_types:
                    error_types[err_key] = []
                error_types[err_key].append(err)
            
            for err_key, err_list in sorted(error_types.items(), key=lambda x: -len(x[1])):
                print(f"  [{err_key}] (共{len(err_list)}次)")
        
        print(f"\n日志文件:")
        print(f"  主日志: {self.main_log_file}")
        print(f"  详细日志: {self.detail_log_file}")
        print(f"  错误日志: {self.error_log_file}")
        print(f"  结果JSON: {self.result_json_file}")


def get_buy_signals_stocks(date: str) -> pd.DataFrame:
    """获取指定日期有买入信号的股票"""
    db_path = Path(__file__).parent.parent.parent / 'data' / 'Astock3.duckdb'
    
    query = f"""
    SELECT 
        code, 
        name, 
        signal_buy_b1, signal_buy_b2, signal_buy_blk, 
        signal_buy_dl, signal_buy_dz30, signal_buy_scb, signal_buy_blkB2 
    FROM daily_signals 
    WHERE date = '{date}' 
    AND (
        signal_buy_b1 OR signal_buy_b2 OR signal_buy_blk OR 
        signal_buy_dl OR signal_buy_dz30 OR signal_buy_scb OR signal_buy_blkB2
    )
    """
    
    try:
        db = duckdb.connect(str(db_path), read_only=True)
        df = db.execute(query).fetchdf()
        db.close()
        return df
    except Exception as e:
        print(f"查询失败: {e}")
        return pd.DataFrame()


def analyze_single_stock(
    stock_code: str, 
    stock_name: str, 
    signal_sources: str,
    trade_date: str,
    logger: AnalysisLogger
) -> Tuple[Dict[str, Any], float]:
    """分析单只股票
    
    Returns:
        (result_dict, duration)
    """
    logger.log_info(f"开始分析", stock_code)
    
    start_time = time.time()
    
    try:
        # 调用分析
        result = analyze_stock(stock_code, trade_date, include_memory=False)
        duration = time.time() - start_time
        
        # 添加股票信息到结果
        result['stock_code'] = stock_code
        result['stock_name'] = stock_name
        result['signal_sources'] = signal_sources
        
        if result.get('success'):
            decision = result.get('final_decision', 'UNKNOWN')
            confidence = result.get('confidence', 0)
            risk_level = 'UNKNOWN'
            position = 0
            
            if result.get('debate_round'):
                risk_level = result.get('debate_round', {}).get('final_risk_level', 'UNKNOWN')
            
            if result.get('trading_signal'):
                position = result.get('trading_signal', {}).get('position_size', 0)
            
            logger.log_info(
                f"分析完成: {decision} (置信度:{confidence}, 风险:{risk_level}, 仓位:{position}) [{duration:.1f}s]",
                stock_code
            )
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.log_error(f"分析失败: {error_msg[:50]}", stock_code)
        
        return result, duration
        
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error(f"分析异常: {str(e)[:50]}", stock_code, e)
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'signal_sources': signal_sources,
            'ai_decision': 'EXCEPTION',
            'ai_confidence': 0,
            'risk_level': 'UNKNOWN',
            'position_size': 0,
            'duration_seconds': round(duration, 2),
            'success': False,
            'error': str(e)
        }, duration


def run_e2e_test(
    test_date: str = '2026-03-27',
    trade_date: str = '2026-03-28'
) -> AnalysisLogger:
    """运行端到端测试
    
    Args:
        test_date: 信号日期
        trade_date: 分析日期
        
    Returns:
        AnalysisLogger实例
    """
    # 创建日志记录器
    run_id = f"e2e_{test_date}_{datetime.now().strftime('%H%M%S')}"
    logger = AnalysisLogger(run_id=run_id)
    
    logger.log_stage_start("E2E_TEST", f"信号日期:{test_date}, 分析日期:{trade_date}")
    
    # Step 1: 查询股票
    logger.log_stage_start("QUERY_STOCKS", "从daily_signals查询买入信号股票")
    stocks_df = get_buy_signals_stocks(test_date)
    logger.log_stage_end("QUERY_STOCKS")
    
    if len(stocks_df) == 0:
        logger.log_warning("未找到符合条件的股票")
        logger.log_stage_end("E2E_TEST")
        return logger
    
    logger.log_info(f"找到 {len(stocks_df)} 只股票有买入信号")
    
    # 打印股票列表
    print("\n股票列表:")
    for idx, row in stocks_df.iterrows():
        signals = []
        for col in ['signal_buy_b1', 'signal_buy_b2', 'signal_buy_blk', 'signal_buy_dl', 'signal_buy_dz30', 'signal_buy_scb', 'signal_buy_blkB2']:
            if row.get(col, False):
                signals.append(col.replace('signal_buy_', '').upper())
        signal_str = '+'.join(signals) if signals else 'NONE'
        print(f"  {row['code']} {row['name']:10} [{signal_str}]")
    print()
    
    # Step 2: 分析每只股票
    logger.log_stage_start("ANALYSIS_LOOP", f"开始分析 {len(stocks_df)} 只股票")
    
    for idx, row in stocks_df.iterrows():
        code = row['code']
        name = row['name']
        
        # 获取信号来源
        signals = []
        for col in ['signal_buy_b1', 'signal_buy_b2', 'signal_buy_blk', 'signal_buy_dl', 'signal_buy_dz30', 'signal_buy_scb', 'signal_buy_blkB2']:
            if row.get(col, False):
                signals.append(col.replace('signal_buy_', '').upper())
        signal_sources = '+'.join(signals) if signals else 'NONE'
        
        logger.log_detail(f"[{idx+1}/{len(stocks_df)}] {code} {name} 信号来源:{signal_sources}", code)
        
        # 分析单只股票
        result, duration = analyze_single_stock(code, name, signal_sources, trade_date, logger)
        
        # 记录结果
        if result.get('success'):
            logger.log_result({
                'stock_code': code,
                'stock_name': name,
                'ai_decision': result.get('final_decision', 'UNKNOWN'),
                'ai_confidence': result.get('confidence', 0),
                'risk_level': result.get('debate_round', {}).get('final_risk_level', 'UNKNOWN') if result.get('debate_round') else 'UNKNOWN',
                'position_size': result.get('trading_signal', {}).get('position_size', 0) if result.get('trading_signal') else 0,
                'duration_seconds': round(duration, 2),
                'signal_sources': signal_sources,
                'success': True,
                'error': ''
            }, duration)
        else:
            logger.log_result({
                'stock_code': code,
                'stock_name': name,
                'ai_decision': 'ERROR',
                'ai_confidence': 0,
                'risk_level': 'UNKNOWN',
                'position_size': 0,
                'duration_seconds': round(duration, 2),
                'signal_sources': signal_sources,
                'success': False,
                'error': result.get('error', 'Unknown error')
            }, duration)
            logger.log_error_result(code, name, result.get('error', 'Unknown error'), duration)
    
    logger.log_stage_end("ANALYSIS_LOOP")
    
    # Step 3: 保存结果
    logger.log_stage_start("SAVE_RESULTS", "保存结果到文件")
    logger.save_results()
    logger.log_stage_end("SAVE_RESULTS")
    
    # 打印汇总
    logger.print_summary()
    
    logger.log_stage_end("E2E_TEST")
    
    return logger


def main():
    """主函数"""
    print("=" * 70)
    print("多Agent系统端到端测试")
    print("=" * 70)
    print()
    
    # 测试参数
    TEST_DATE = '2026-03-27'  # 信号日期
    TRADE_DATE = '2026-03-28'  # 分析日期
    
    print(f"信号日期: {TEST_DATE}")
    print(f"分析日期: {TRADE_DATE}")
    print()
    
    # 运行测试
    logger = run_e2e_test(TEST_DATE, TRADE_DATE)
    
    print("\n测试完成!")


if __name__ == '__main__':
    main()
