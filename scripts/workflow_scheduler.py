#!/usr/bin/env python3
"""
A股数据流水线调度器

提供数据流水线的创建、运行、状态查看、失败重试等功能。
"""

import argparse
import logging
import sys
import os
from typing import Dict, Any
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb

# 导入流水线管理模块
from scripts.pipeline_manager import (
    get_or_create_pipeline,
    find_next_step,
    update_step_status,
    write_step_log,
    get_pipeline_steps,
    get_last_success_date,
    STEP_DEPENDENCIES,
)

# 导入数据更新模块
from signals.scan_signals_v2 import scan_signals

# 导入健康检查模块
from scripts.data_check.health_check import check_all_sources, get_optimal_source

from config.settings import Settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据库路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'Astock3.duckdb')

# 导入数据库工具
from scripts.db_utils import get_db_connection, DB_PATH as DB_PATH_CONST


def get_pipeline_summary(pipeline_id: str, today: str) -> Dict[str, Any]:
    """
    初始化流水线状态摘要字典

    Args:
        pipeline_id: 流水线ID
        today: 日期字符串

    Returns:
        dict: 包含流水线基础状态的字典
    """
    from datetime import datetime as dt
    return {
        "pipeline_id": pipeline_id,
        "date": today,
        "status": "no_data",
        "notify_required": False,
        "xiaoji_check_time": dt.now().isoformat()
    }


def format_step_status(steps: list) -> tuple:
    """
    格式化步骤状态列表

    Args:
        steps: 流水线步骤列表

    Returns:
        tuple: (step_status dict, last_step str, has_failed bool, total_duration float)
    """
    step_status = {}
    last_step = None
    has_failed = False
    total_duration = 0.0

    for step in sorted(steps, key=lambda x: x.get('step_order', 0)):
        step_name = step.get('step_name', '')
        step_status[step_name] = {
            "status": step.get('status', 'unknown'),
            "records": step.get('records_count'),
            "duration": step.get('duration_sec'),
            "error": step.get('error_message') if step.get('status') == 'failed' else None
        }
        if step.get('status') == 'success':
            last_step = step_name
            total_duration += step.get('duration_sec', 0) or 0
        if step.get('status') == 'failed':
            has_failed = True

    return step_status, last_step, has_failed, total_duration


def check_pipeline_health(steps: list, has_failed: bool, last_step: str) -> tuple:
    """
    检查流水线健康状态

    Args:
        steps: 流水线步骤列表
        has_failed: 是否有失败的步骤
        last_step: 最后一个成功的步骤名

    Returns:
        tuple: (status str, last_success_step str or None, error str or None)
    """
    if has_failed:
        # 找到失败的步骤和错误信息
        error = None
        for step in steps:
            if step.get('status') == 'failed':
                error = step.get('error_message')
                break
        return "failed", last_step, error

    # 没有失败，检查是否所有步骤都完成
    all_done = all(s.get('status') in ('success', 'skipped') for s in steps)
    status = "success" if all_done else "running"
    return status, None, None


def get_step_params(pipeline_id: str, step_name: str) -> Dict[str, Any]:
    """获取步骤参数"""
    import json
    with get_db_connection() as conn:
        # 先从 pipeline 表获取 target_date
        row = conn.execute("""
            SELECT params FROM data_pipeline_run
            WHERE pipeline_id = ? AND step_name = 'stock_info'
            LIMIT 1
        """, [pipeline_id]).fetchone()
        
        if row and row[0]:
            params = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            # 返回正确的日期格式
            return {
                'target_date': params.get('target_date'),  # YYYY-MM-DD
                'target_date_YYYYMMDD': params.get('target_date_YYYYMMDD'),  # YYYYMMDD
                'start_date': params.get('target_date_YYYYMMDD'),  # daily_price 需要 YYYYMMDD
                'end_date': params.get('target_date_YYYYMMDD'),    # daily_price 需要 YYYYMMDD
                'trading_date': params.get('target_date'),        # signals 需要 YYYY-MM-DD
                'mode': 'incremental',  # 增量更新模式
            }
        return {}


def run_step_stock_info(pipeline_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 stock_info 步骤"""
    start_time = datetime.now()
    
    # 从环境变量获取数据源，默认tushare
    source = os.environ.get('DATA_SOURCE', 'tushare')
    
    # 使用 DWDFetcher
    from data.updaters.fetcher_dwd import DWDFetcher
    fetcher = DWDFetcher(source=source)
    result = fetcher.update_stock_info(source=source)
    
    with get_db_connection() as conn:
        actual_count = conn.execute("SELECT COUNT(*) FROM dwd_stock_info WHERE list_status = 'L'").fetchone()[0]
    
    write_step_log(pipeline_id, 'stock_info', {
        'update_type': 'full',
        'start_time': start_time.isoformat(),
        'end_time': datetime.now().isoformat(),
        'expected_count': result.get('records', 0),
        'actual_count': actual_count,
        'is_success': result.get('success', 0) == 1,
        'data_source': source,
        'step_details': {
            'elapsed': result.get('elapsed', 0),
        }
    })
    
    return {'success': True, 'records_count': actual_count}


def run_step_daily_price(pipeline_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 daily_price 步骤"""
    start_time = datetime.now()
    start_date = params.get('start_date', datetime.now().strftime('%Y%m%d'))
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
    processes = params.get('processes', 10)
    
    # 使用 fetcher_dwd.DWDFetcher
    from data.updaters.fetcher_dwd import DWDFetcher
    
    # 从环境变量获取数据源，默认tushare
    source = os.environ.get('DATA_SOURCE', 'tushare')
    fetcher = DWDFetcher(source=source)
    
    # 按数据源选择下载方式
    if source == 'baostock':
        # baostock按股票下载
        result = fetcher.update_daily_by_stock(start_date, end_date, num_workers=processes)
    elif source == 'tushare':
        # tushare按日期下载
        result = fetcher.update_daily(start_date, end_date)
    
    with get_db_connection() as conn:
        actual_count = conn.execute("SELECT COUNT(*) FROM dwd_daily_price").fetchone()[0]
        stock_count = conn.execute("SELECT COUNT(DISTINCT ts_code) FROM dwd_daily_price").fetchone()[0]
    
    write_step_log(pipeline_id, 'daily_price', {
        'start_time': start_time.isoformat(),
        'end_time': datetime.now().isoformat(),
        'start_date': start_date,
        'end_date': end_date,
        'actual_count': actual_count,
        'stock_count': stock_count,
        'source': source,
        'is_success': True,
        'step_details': result
    })
    
    return {'success': True, 'records_count': actual_count}


def run_step_signals(pipeline_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 signals 步骤"""
    start_time = datetime.now()
    trading_date = params.get('trading_date', datetime.now().strftime('%Y%m%d'))
    workers = params.get('workers', 10)
    
    result = scan_signals(trading_date=trading_date, workers=workers)
    
    write_step_log(pipeline_id, 'signals', {
        'start_time': start_time.isoformat(),
        'end_time': datetime.now().isoformat(),
        'trading_date': trading_date,
        'is_success': True,
        'step_details': result
    })
    
    return {'success': True, 'records_count': result.get('total_signals', 0)}


def run_step_trade(pipeline_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """执行 trade 步骤 (stub)"""
    update_step_status(pipeline_id, 'trade', 'skipped')
    return {'success': True, 'records_count': 0}


STEP_HANDLERS = {
    'stock_info': run_step_stock_info,
    'daily_price': run_step_daily_price,
    'signals': run_step_signals,
    'trade': run_step_trade,
}


def run_step(pipeline_id: str, step_name: str) -> Dict[str, Any]:
    """运行单个步骤"""
    logger.info(f"运行步骤: {pipeline_id} - {step_name}")
    
    params = get_step_params(pipeline_id, step_name)
    
    handler = STEP_HANDLERS.get(step_name)
    if not handler:
        return {'success': False, 'error': f'Unknown step: {step_name}'}
    
    return handler(pipeline_id, params)


def run_pipeline(pipeline_id: str, skip_health_check: bool = False, force_source: str = None) -> bool:
    """运行流水线
    
    Args:
        pipeline_id: 流水线ID
        skip_health_check: 是否跳过健康检查
        force_source: 强制使用的数据源 (tushare/akshare/baostock)
    """
    logger.info(f"开始运行流水线: {pipeline_id}")
    
    # 健康检查
    if not skip_health_check:
        logger.info("执行数据源健康检查...")
        results = check_all_sources()
        for source, result in results.items():
            status = "✅ 可用" if result["available"] else "❌ 不可用"
            rt = f"{result['response_time']}s" if result["response_time"] else "N/A"
            logger.info(f"  {source}: {status} (响应时间: {rt})")
        
        # 确定使用的数据源
        if force_source:
            recommended_source = force_source
            logger.info(f"强制使用数据源: {recommended_source}")
        else:
            recommended_source = get_optimal_source(results)
            logger.info(f"推荐数据源: {recommended_source}")
        
        if recommended_source:
            Settings.DATA_SOURCE = recommended_source
            logger.info(f"已设置 DATA_SOURCE = {recommended_source}")
        else:
            logger.warning("没有可用的数据源，将使用默认配置")
    
    # 设置环境变量供下游使用
    if force_source:
        os.environ['DATA_SOURCE'] = force_source
    elif not skip_health_check:
        os.environ['DATA_SOURCE'] = Settings.DATA_SOURCE
    
    while True:
        step = find_next_step(pipeline_id)
        if not step:
            logger.info(f"流水线 {pipeline_id} 完成，没有更多步骤")
            break
        
        step_name = step['step_name']
        logger.info(f"执行步骤: {step_name}")
        
        update_step_status(pipeline_id, step_name, 'running')
        
        try:
            result = run_step(pipeline_id, step_name)
            if result.get('success'):
                update_step_status(pipeline_id, step_name, 'success', **result)
                logger.info(f"步骤 {step_name} 成功")
            else:
                update_step_status(pipeline_id, step_name, 'failed', error_message=result.get('error', 'Unknown error'))
                logger.error(f"步骤 {step_name} 失败: {result.get('error')}")
                break
        except Exception as e:
            logger.exception(f"步骤 {step_name} 执行异常")
            update_step_status(pipeline_id, step_name, 'failed', error_message=str(e))
            break
    
    return True


def parse_args():
    parser = argparse.ArgumentParser(
        prog='workflow_scheduler.py',
        description='A股数据流水线调度器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python scripts/workflow_scheduler.py --run --pipeline daily --date 20260323
  python scripts/workflow_scheduler.py --status
  python scripts/workflow_scheduler.py --check-only --step step_02
  python scripts/workflow_scheduler.py --restart --step step_03
  python scripts/workflow_scheduler.py --xiaoji-check --date 20260323
        '''
    )
    
    parser.add_argument(
        '--pipeline',
        choices=['daily', 'weekly'],
        default='daily',
        help='流水线名称 (daily/weekly), 默认: daily'
    )
    parser.add_argument(
        '--run',
        action='store_true',
        help='创建并运行新流水线'
    )
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='仅检查并运行下一步，不创建新流水线'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='查看流水线状态'
    )
    parser.add_argument(
        '--restart',
        action='store_true',
        help='重新运行失败的步骤'
    )
    parser.add_argument(
        '--step',
        type=str,
        help='指定从哪个步骤开始'
    )
    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='指定交易日期 (YYYYMMDD), 默认: 今天'
    )
    parser.add_argument(
        '--xiaoji-check',
        action='store_true',
        help='小金监控接口（返回 JSON）'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细日志'
    )
    parser.add_argument(
        '--skip-health-check',
        action='store_true',
        help='跳过数据源健康检查'
    )
    parser.add_argument(
        '--force-source',
        type=str,
        choices=['tushare', 'akshare', 'baostock'],
        help='强制使用指定数据源'
    )
    
    return parser.parse_args()


def show_pipeline_status(pipeline_id: str):
    """显示流水线状态"""
    steps = get_pipeline_steps(pipeline_id)
    
    print(f"\n流水线: {pipeline_id}")
    print("-" * 60)
    print(f"{'步骤名称':<15} {'状态':<10} {'更新时间':<20}")
    print("-" * 60)
    
    for step in steps:
        status = step['status']
        completed = step.get('completed_at')
        time_str = completed.strftime('%Y-%m-%d %H:%M:%S') if completed else 'N/A'
        records = step.get('records_count', 'N/A')
        print(f"{step['step_name']:<15} {status:<10} {time_str:<20} 记录:{records}")
    
    print("-" * 60)
    
    dependencies = STEP_DEPENDENCIES
    print("\n步骤依赖:")
    for step, deps in dependencies.items():
        deps_str = deps if deps else '(无依赖)'
        print(f"  {step}: {deps_str}")


def xiaoji_check(date: str = None) -> dict:
    """
    小金监控接口 - 返回流水线状态（JSON格式）
    
    Args:
        date: 可选，指定日期，默认今天
        
    Returns:
        dict: 包含流水线状态的字典，用于 JSON 输出
    """
    from datetime import datetime
    from scripts.pipeline_manager import (
        get_pipeline_steps,
        get_or_create_pipeline,
        get_monitor_flag,
        set_monitor_flag_completed,
        reset_monitor_flag_if_new_day,
        is_pipeline_all_success,
    )
    
    today = date or datetime.now().strftime('%Y%m%d')
    
    result = {
        "pipeline_id": None,
        "date": today,
        "status": "no_data",
        "notify_required": False,
        "xiaoji_check_time": datetime.now().isoformat()
    }
    
    # 新一天则重置标志
    reset_monitor_flag_if_new_day(today)
    
    # 检查是否已完成监控
    flag = get_monitor_flag(today)
    if flag and flag.get('completed'):
        result["status"] = "completed"
        result["completed_at"] = flag.get('completed_at').isoformat() if flag.get('completed_at') else None
        result["notify_required"] = False
        result["message"] = "流水线已完成，今日停止监控"
        return result
    
    # 先用 get_or_create_pipeline 获取实际 pipeline_id（支持 LIKE 匹配带后缀的 ID）
    pipeline_info = get_or_create_pipeline("daily", today)
    pipeline_id = pipeline_info['pipeline_id']
    result["pipeline_id"] = pipeline_id
    
    # 查询今日流水线状态
    steps = get_pipeline_steps(pipeline_id)
    if not steps:
        # 无今日数据，查询最后成功日期
        from scripts.pipeline_manager import get_last_success_date
        try:
            last_success = get_last_success_date()
            if last_success:
                result["last_success_date"] = last_success.isoformat() if hasattr(last_success, 'isoformat') else str(last_success)
                days_diff = (datetime.now().date() - last_success).days
                result["notify_required"] = True
                result["message"] = f"{days_diff}天未更新数据，请检查"
        except Exception as e:
            logger.error(f"获取最后成功日期失败: {e}")
            result["message"] = "无法获取最后成功日期"
        return result
    
    # 检查是否所有步骤都成功 → 完成监控
    if is_pipeline_all_success(pipeline_id):
        set_monitor_flag_completed(today)
        result["status"] = "all_success"
        result["notify_required"] = True
        result["message"] = "✅ 数据流水线全部步骤执行完成，今日停止监控"
        return result
    
    # 构建步骤状态
    step_status, last_step, has_failed, total_duration = format_step_status(steps)

    result["pipeline_id"] = pipeline_id
    result["steps"] = step_status
    result["last_step"] = last_step
    result["total_duration"] = total_duration

    # 检查流水线健康状态
    status, last_success_step, error = check_pipeline_health(steps, has_failed, last_step)

    if has_failed:
        result["failed_step"] = last_step
        result["error"] = error

    result["status"] = status
    result["last_success_step"] = last_success_step
    result["notify_required"] = True
    
    return result


def main():
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.debug(f"解析的参数: {args}")
    
    if args.xiaoji_check:
        import json
        result = xiaoji_check(args.date)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    date_str = args.date
    if len(date_str) == 8:
        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    
    if args.status:
        pipeline_info = get_or_create_pipeline(args.pipeline, args.date)
        pipeline_id = pipeline_info['pipeline_id']
        show_pipeline_status(pipeline_id)
        return
    
    if args.restart:
        logger.info(f"重新运行失败步骤: {args.pipeline}, 从 {args.step} 开始")
        return
    
    if args.check_only:
        logger.info(f"检查并运行下一步: {args.pipeline}, 从 {args.step or '下一步'} 开始")
        return
    
    if args.run:
        pipeline_info = get_or_create_pipeline(args.pipeline, args.date)
        pipeline_id = pipeline_info['pipeline_id']
        logger.info(f"创建并运行新流水线: {pipeline_id}")
        run_pipeline(pipeline_id, skip_health_check=args.skip_health_check, force_source=args.force_source)
        return
    
    logger.error("请指定操作: --run, --check-only, --status, --restart, 或 --xiaoji-check")
    sys.exit(1)


if __name__ == '__main__':
    main()
