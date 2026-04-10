"""
结果适配器 - ResultAdapter实现
"""
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    from database.db_manager import DatabaseManager
except ImportError:
    DatabaseManager = None


class ResultAdapter:
    """结果适配器
    
    将分析结果保存到DuckDB数据库。
    """
    
    TABLE_NAME = 'agent_analysis_results'
    
    def __init__(self, db_path: str = None):
        """初始化结果适配器
        
        Args:
            db_path: 数据库路径，默认使用项目数据库
        """
        self._db = None
        self._db_path = db_path
        self._ensure_table()
    
    def _get_db(self):
        """获取数据库连接"""
        if self._db is None and DatabaseManager:
            try:
                self._db = DatabaseManager(self._db_path)
            except Exception as e:
                print(f"数据库连接失败: {e}")
                return None
        return self._db
    
    def _ensure_table(self):
        """确保表存在"""
        db = self._get_db()
        if db is None:
            return
        
        try:
            db.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    run_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR,
                    trade_date VARCHAR,
                    result_json TEXT,
                    created_at TIMESTAMP
                )
            """)
        except Exception as e:
            print(f"创建表失败: {e}")
    
    def save_analysis_result(self, symbol: str, trade_date: str, result: Dict[str, Any]) -> str:
        """保存分析结果
        
        Args:
            symbol: 股票代码
            trade_date: 交易日期
            result: 分析结果字典
            
        Returns:
            run_id: 唯一标识符
        """
        run_id = f"ANA_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        db = self._get_db()
        if db is None:
            return run_id
        
        try:
            result_json = json.dumps(result, ensure_ascii=False, indent=2)
            
            db.conn.execute(f"""
                INSERT INTO {self.TABLE_NAME} (run_id, symbol, trade_date, result_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, [run_id, symbol, trade_date, result_json, datetime.now()])
            
        except Exception as e:
            print(f"保存分析结果失败: {e}")
        
        return run_id
    
    def load_analysis_result(self, run_id: str) -> Optional[Dict[str, Any]]:
        """加载分析结果
        
        Args:
            run_id: 唯一标识符
            
        Returns:
            分析结果字典
        """
        db = self._get_db()
        if db is None:
            return None
        
        try:
            df = db.conn.execute(f"""
                SELECT result_json FROM {self.TABLE_NAME}
                WHERE run_id = ?
            """, [run_id]).fetchdf()
            
            if len(df) > 0:
                return json.loads(df.iloc[0]['result_json'])
            
        except Exception as e:
            print(f"加载分析结果失败: {e}")
        
        return None
    
    def get_analysis_history(self, symbol: str = None, start_date: str = None, end_date: str = None, offset: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
        """获取分析历史
        
        Args:
            symbol: 股票代码过滤，None表示所有
            start_date: 开始日期，格式YYYY-MM-DD
            end_date: 结束日期，格式YYYY-MM-DD
            offset: 偏移量，用于分页
            limit: 返回数量限制
            
        Returns:
            分析结果列表
        """
        db = self._get_db()
        if db is None:
            return []
        
        try:
            conditions = []
            params = []
            
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
            
            if start_date:
                conditions.append("created_at >= ?")
                params.append(start_date)
            
            if end_date:
                conditions.append("created_at <= ?")
                params.append(end_date)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params.extend([limit, offset])
            
            df = db.conn.execute(f"""
                SELECT run_id, symbol, trade_date, created_at, result_json
                FROM {self.TABLE_NAME}
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params).fetchdf()
            
            results = []
            for _, row in df.iterrows():
                try:
                    result_data = json.loads(row['result_json'])
                except:
                    result_data = {}
                
                results.append({
                    'run_id': row['run_id'],
                    'symbol': row['symbol'],
                    'trade_date': row['trade_date'],
                    'created_at': str(row['created_at']),
                    'result': result_data
                })
            
            return results
            
        except Exception as e:
            print(f"获取分析历史失败: {e}")
            return []
    
    def delete_analysis_result(self, run_id: str) -> bool:
        """删除分析结果
        
        Args:
            run_id: 唯一标识符
            
        Returns:
            是否成功
        """
        db = self._get_db()
        if db is None:
            return False
        
        try:
            db.conn.execute(f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE run_id = ?
            """, [run_id])
            return True
        except Exception as e:
            print(f"删除分析结果失败: {e}")
            return False


def get_result_adapter(db_path: str = None) -> ResultAdapter:
    """获取结果适配器实例"""
    return ResultAdapter(db_path)