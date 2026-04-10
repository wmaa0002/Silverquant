"""
流水线状态管理模块

管理数据处理流水线的状态、步骤依赖和日志记录。
"""

import duckdb
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import random

DB_PATH = 'data/Astock3.duckdb'

# 步骤依赖定义
STEP_DEPENDENCIES = {
    'stock_info': None,
    'daily_price': 'stock_info',
    'signals': 'daily_price',
    'trade': 'signals',
}

STEP_ORDER = {
    'stock_info': 1,
    'daily_price': 2,
    'signals': 3,
    'trade': 4,
}


def _get_conn(read_only: bool = False):
    """获取数据库连接"""
    return duckdb.connect(DB_PATH, read_only=read_only)


def init_pipeline(pipeline_name: str, date: str) -> str:
    """
    初始化新流水线，插入4个步骤记录，返回 pipeline_id
    """
    conn = _get_conn()
    try:
        # 生成 pipeline_id (不重复的)
        suffix = random.randint(1000, 9999)
        pipeline_id = f"{pipeline_name}_{date}_{suffix}"
        
        max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM data_pipeline_run").fetchone()[0]
        next_id = max_id + 1
        
        # 将日期转换为 YYYY-MM-DD 格式存储在 params 中
        date_formatted = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        params = json.dumps({"target_date": date_formatted, "target_date_YYYYMMDD": date})
        
        # 插入4个步骤记录
        for i, (step_name, step_order) in enumerate(STEP_ORDER.items()):
            conn.execute("""
                INSERT INTO data_pipeline_run (
                    id, pipeline_id, pipeline_name, step_name, step_order,
                    status, depends_on, created_at, params
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """, [next_id + i, pipeline_id, pipeline_name, step_name, step_order, 
                  STEP_DEPENDENCIES.get(step_name), datetime.now(), params])
        
        return pipeline_id
    finally:
        conn.close()


def get_or_create_pipeline(pipeline_name: str, date: str) -> Dict[str, Any]:
    """
    获取或创建今日流水线
    """
    conn = _get_conn()
    try:
        # 尝试查找指定日期的流水线
        pipeline_id_pattern = f"{pipeline_name}_{date}_%"
        row = conn.execute("""
            SELECT pipeline_id, pipeline_name, step_name, step_order, status, depends_on
            FROM data_pipeline_run
            WHERE pipeline_id LIKE ? AND step_name = 'stock_info'
            ORDER BY created_at DESC
            LIMIT 1
        """, [pipeline_id_pattern]).fetchone()
        
        if row:
            return {
                'pipeline_id': row[0],
                'pipeline_name': row[1],
                'step_name': row[2],
                'step_order': row[3],
                'status': row[4],
                'depends_on': row[5],
            }
        
        # 不存在则创建新流水线
        pipeline_id = init_pipeline(pipeline_name, date)
        return get_or_create_pipeline(pipeline_name, date)
    finally:
        conn.close()


def get_pipeline_steps(pipeline_id: str) -> List[Dict[str, Any]]:
    """
    查询流水线所有步骤
    """
    conn = _get_conn(read_only=True)
    try:
        rows = conn.execute("""
            SELECT id, pipeline_id, step_name, step_order, status, 
                   started_at, completed_at, duration_sec, records_count, error_message
            FROM data_pipeline_run
            WHERE pipeline_id = ?
            ORDER BY step_order
        """, [pipeline_id]).fetchall()
        
        return [
            {
                'id': row[0],
                'pipeline_id': row[1],
                'step_name': row[2],
                'step_order': row[3],
                'status': row[4],
                'started_at': row[5],
                'completed_at': row[6],
                'duration_sec': row[7],
                'records_count': row[8],
                'error_message': row[9],
            }
            for row in rows
        ]
    finally:
        conn.close()


def update_step_status(
    pipeline_id: str,
    step_name: str,
    status: str,
    **kwargs
) -> bool:
    """
    更新步骤状态
    """
    valid_statuses = {'pending', 'running', 'success', 'failed', 'skipped'}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}")
    
    conn = _get_conn()
    try:
        now = datetime.now()
        
        if status == 'running':
            conn.execute("""
                UPDATE data_pipeline_run
                SET status = ?, started_at = ?
                WHERE pipeline_id = ? AND step_name = ?
            """, [status, now, pipeline_id, step_name])
        elif status in ('success', 'failed', 'skipped'):
            conn.execute("""
                UPDATE data_pipeline_run
                SET status = ?, completed_at = ?,
                    records_count = ?, error_message = ?
                WHERE pipeline_id = ? AND step_name = ?
            """, [
                status, now,
                kwargs.get('records_count'),
                kwargs.get('error_message'),
                pipeline_id, step_name
            ])
        else:
            conn.execute("""
                UPDATE data_pipeline_run
                SET status = ?
                WHERE pipeline_id = ? AND step_name = ?
            """, [status, pipeline_id, step_name])
        
        return True
    finally:
        conn.close()


def write_step_log(pipeline_id: str, step_name: str, log_data: Dict[str, Any]) -> bool:
    """
    写入 step_update_log
    """
    conn = _get_conn()
    try:
        max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM step_update_log").fetchone()[0]
        next_id = max_id + 1
        
        conn.execute("""
            INSERT INTO step_update_log (
                id, pipeline_id, step_name, update_type,
                start_time, end_time, duration_sec,
                expected_count, actual_count, is_success,
                error_message, error_details, step_details, validation_results
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            next_id,
            pipeline_id,
            step_name,
            log_data.get('update_type'),
            log_data.get('start_time'),
            log_data.get('end_time'),
            log_data.get('duration_sec'),
            log_data.get('expected_count'),
            log_data.get('actual_count'),
            log_data.get('is_success'),
            log_data.get('error_message'),
            json.dumps(log_data.get('error_details')) if log_data.get('error_details') else None,
            json.dumps(log_data.get('step_details')) if log_data.get('step_details') else None,
            json.dumps(log_data.get('validation_results')) if log_data.get('validation_results') else None,
        ])
        return True
    finally:
        conn.close()


def find_next_step(pipeline_id: str) -> Optional[Dict[str, Any]]:
    """
    找到下一个待执行步骤
    """
    conn = _get_conn(read_only=True)
    try:
        # 获取所有 pending 步骤
        rows = conn.execute("""
            SELECT id, pipeline_id, step_name, step_order, status, depends_on
            FROM data_pipeline_run
            WHERE pipeline_id = ? AND status = 'pending'
            ORDER BY step_order
        """, [pipeline_id]).fetchall()
        
        for row in rows:
            step_name = row[2]
            depends_on = row[5]
            
            # 检查依赖是否满足
            if depends_on is None:
                return {
                    'id': row[0],
                    'pipeline_id': row[1],
                    'step_name': step_name,
                    'step_order': row[3],
                    'status': row[4],
                    'depends_on': depends_on,
                }
            
            # 检查依赖步骤是否成功
            dep_row = conn.execute("""
                SELECT status FROM data_pipeline_run
                WHERE pipeline_id = ? AND step_name = ?
            """, [pipeline_id, depends_on]).fetchone()
            
            if dep_row and dep_row[0] == 'success':
                return {
                    'id': row[0],
                    'pipeline_id': row[1],
                    'step_name': step_name,
                    'step_order': row[3],
                    'status': row[4],
                    'depends_on': depends_on,
                }
        
        return None
    finally:
        conn.close()


def check_dependency_met(step_name: str, pipeline_id: str) -> bool:
    """
    检查前置依赖是否满足
    """
    dependencies = STEP_DEPENDENCIES.get(step_name)
    
    if dependencies is None:
        return True
    
    conn = _get_conn(read_only=True)
    try:
        row = conn.execute("""
            SELECT status FROM data_pipeline_run
            WHERE pipeline_id = ? AND step_name = ?
        """, [pipeline_id, dependencies]).fetchone()
        
        return row is not None and row[0] == 'success'
    finally:
        conn.close()


def get_last_success_date() -> Optional[datetime]:
    """
    获取最后成功完成的流水线日期
    """
    conn = _get_conn(read_only=True)
    try:
        # 查找所有流水线中，所有步骤都成功的最新日期
        row = conn.execute("""
            SELECT pipeline_id, pipeline_name
            FROM data_pipeline_run
            WHERE step_name = 'trade' AND status = 'success'
            ORDER BY completed_at DESC
            LIMIT 1
        """).fetchone()
        
        if row:
            pipeline_id = row[0]
            # 从 pipeline_id 提取日期
            parts = pipeline_id.split('_')
            if len(parts) >= 2:
                date_str = parts[1]
                return datetime.strptime(date_str, '%Y%m%d').date()
        return None
    finally:
        conn.close()


def get_monitor_flag(date: str) -> Optional[Dict[str, Any]]:
    """
    获取指定日期的监控完成标志
    
    Args:
        date: YYYYMMDD 格式
        
    Returns:
        dict: {'completed': bool, 'completed_at': datetime} 或 None
    """
    conn = _get_conn(read_only=True)
    try:
        row = conn.execute("""
            SELECT completed, completed_at
            FROM pipeline_monitor_flag
            WHERE date = ?
            LIMIT 1
        """, [date]).fetchone()
        
        if row:
            return {
                'completed': bool(row[0]),
                'completed_at': row[1],
            }
        return None
    finally:
        conn.close()


def set_monitor_flag_completed(date: str) -> bool:
    """
    标记指定日期的流水线已完成监控
    
    Args:
        date: YYYYMMDD 格式
        
    Returns:
        bool: 是否成功
    """
    conn = _get_conn()
    try:
        # 先检查是否存在
        existing = conn.execute("""
            SELECT id FROM pipeline_monitor_flag WHERE date = ?
        """, [date]).fetchone()
        
        now = datetime.now()
        if existing:
            conn.execute("""
                UPDATE pipeline_monitor_flag
                SET completed = TRUE, completed_at = ?
                WHERE date = ?
            """, [now, date])
        else:
            max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM pipeline_monitor_flag").fetchone()[0]
            conn.execute("""
                INSERT INTO pipeline_monitor_flag (id, date, completed, completed_at)
                VALUES (?, ?, TRUE, ?)
            """, [max_id + 1, date, now])
        return True
    finally:
        conn.close()


def reset_monitor_flag_if_new_day(date: str) -> bool:
    """
    如果传入日期与表中记录的日期不同，重置标志（新的一天）
    
    Args:
        date: YYYYMMDD 格式
        
    Returns:
        bool: 是否执行了重置
    """
    conn = _get_conn()
    try:
        row = conn.execute("""
            SELECT id, date FROM pipeline_monitor_flag ORDER BY id DESC LIMIT 1
        """).fetchone()
        
        if row and row[1] != date:
            # 新的一天，删除旧记录
            conn.execute("DELETE FROM pipeline_monitor_flag WHERE date = ?", [row[1]])
            return True
        return False
    finally:
        conn.close()


def is_pipeline_all_success(pipeline_id: str) -> bool:
    """
    检查流水线所有步骤是否都成功
    
    Args:
        pipeline_id: 流水线ID
        
    Returns:
        bool: 所有步骤都成功返回 True
    """
    conn = _get_conn(read_only=True)
    try:
        rows = conn.execute("""
            SELECT status FROM data_pipeline_run
            WHERE pipeline_id = ?
        """, [pipeline_id]).fetchall()
        
        if not rows:
            return False
        
        return all(row[0] == 'success' for row in rows)
    finally:
        conn.close()
