"""
数据库管理器 - DuckDB操作封装
"""
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import json


class DatabaseManager:
    """DuckDB数据库管理器"""
    
    _instance = None
    
    def __new__(cls, db_path: str = None):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = None):
        if self._initialized:
            return
            
        if db_path is None:
            # 默认数据库路径
            db_path = Path(__file__).parent.parent / 'data' / 'Astock3.duckdb'
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 建立连接
        self.conn = duckdb.connect(str(self.db_path))
        
        # 初始化表结构
        from .schema import create_tables
        create_tables(self.conn)
        
        self._initialized = True
        print(f"数据库连接成功: {self.db_path}")
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            print("数据库连接已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ==================== 股票基础信息操作 ====================
    
    def save_stock_info(self, df: pd.DataFrame):
        """保存股票基础信息到 dwd_stock_info
        
        字段映射:
          code → symbol (股票代码如 600000)
          code → ts_code (tushare格式如 600000.SH)
          name → name
          industry → industry
          listing_date → list_date
          market_cap / update_time 等旧表字段：dwd_stock_info 无对应字段，自动丢弃
        """
        if len(df) == 0:
            return
            
        df = df.copy()
        
        # 构建 ts_code (tushare 格式: 600000.SH / 000001.SZ)
        def code_to_ts_code(code):
            code = str(code)
            return f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
        df['ts_code'] = df['code'].apply(code_to_ts_code)
        
        # 字段重命名对齐 dwd_stock_info schema
        df['symbol'] = df['code']
        df['list_date'] = df['listing_date']
        df['data_source'] = 'stock_info_updater'
        
        insert_cols = ['ts_code', 'symbol', 'name', 'industry', 'list_date', 'data_source']
        
        self.conn.execute("""
            CREATE TEMPORARY TABLE temp_stock_info AS SELECT * FROM df;
        """)
        
        update_parts = [f"{c} = excluded.{c}" for c in insert_cols if c not in ['ts_code', 'symbol']]
        if update_parts:
            upsert_sql = f"""
                INSERT INTO dwd_stock_info ({', '.join(insert_cols)})
                SELECT {', '.join(insert_cols)} FROM temp_stock_info
                ON CONFLICT (ts_code) DO UPDATE SET
                    {', '.join(update_parts)};
            """
        else:
            upsert_sql = f"""
                INSERT INTO dwd_stock_info ({', '.join(insert_cols)})
                SELECT {', '.join(insert_cols)} FROM temp_stock_info
                ON CONFLICT (ts_code) DO NOTHING;
            """
        
        self.conn.execute(upsert_sql)
        self.conn.execute("DROP TABLE temp_stock_info;")
        print(f"已保存 {len(df)} 条股票基础信息到 dwd_stock_info")
    
    def get_stock_info(self, code: Optional[str] = None) -> pd.DataFrame:
        """获取股票基础信息（从 dwd_stock_info 读取）
        
        返回字段与旧 stock_info 表 schema 一致:
          code, name, industry, market_cap, circulating_cap, 
          listing_date, market_type, is_st, update_time, is_delisted
        
        注意: market_cap, circulating_cap, is_st, update_time, is_delisted 
              在 dwd_stock_info 中无对应字段，返回时为 NULL
        """
        if code:
            ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            query = f"""
                SELECT 
                    symbol AS code,
                    name,
                    industry,
                    NULL AS market_cap,
                    NULL AS circulating_cap,
                    list_date AS listing_date,
                    market AS market_type,
                    NULL AS is_st,
                    NULL AS update_time,
                    (list_status = 'D') AS is_delisted
                FROM dwd_stock_info 
                WHERE ts_code = '{ts_code}'
            """
        else:
            query = """
                SELECT 
                    symbol AS code,
                    name,
                    industry,
                    NULL AS market_cap,
                    NULL AS circulating_cap,
                    list_date AS listing_date,
                    market AS market_type,
                    NULL AS is_st,
                    NULL AS update_time,
                    (list_status = 'D') AS is_delisted
                FROM dwd_stock_info
            """
        return self.conn.execute(query).fetchdf()
    
    def get_stock_list(self) -> List[str]:
        """获取所有股票代码列表（从 dwd_stock_info 读取）"""
        result = self.conn.execute("SELECT symbol FROM dwd_stock_info WHERE list_status = 'L' ORDER BY symbol").fetchall()
        return [row[0] for row in result]
    
    # ==================== 价格数据操作 ====================
    
    def save_daily_price(self, df: pd.DataFrame):
        """保存日线数据"""
        if len(df) == 0:
            return
            
        # 确保列名正确
        df = df.copy()
        if 'datetime' in df.columns:
            df['date'] = pd.to_datetime(df['datetime']).dt.date
        
        required_cols = ['date', 'code', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"缺少必需列: {col}")
        
        # 确保所有必需列存在
        for col in ['amount', 'amplitude', 'pct_change', 'change_amount', 'turnover', 'adj_factor']:
            if col not in df.columns:
                df[col] = 0.0
        
        # 字段映射：外部列名 → dwd_daily_price列名
        # date → trade_date, code → ts_code, volume → vol, pct_change → pct_chg
        df['trade_date'] = df['date']
        
        def code_to_ts_code(code):
            """转换股票代码为tushare格式"""
            code = str(code)
            if code.startswith('6'):
                return f"{code}.SH"
            else:
                return f"{code}.SZ"
        
        df['ts_code'] = df['code'].apply(code_to_ts_code)
        df['vol'] = df['volume']
        df['pct_chg'] = df['pct_change']
        df['data_source'] = 'daily_update'
        
        # 使用INSERT OR REPLACE
        self.conn.execute("""
            CREATE TEMPORARY TABLE temp_price AS SELECT * FROM df;
            
            INSERT OR REPLACE INTO dwd_daily_price 
            SELECT trade_date, ts_code, open, high, low, close, vol,
                   amount, amplitude, pct_chg, change_amount, 
                   turnover, adj_factor, data_source
            FROM temp_price;
            
            DROP TABLE temp_price;
        """)
    
    def get_daily_price(
        self, 
        code: str, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """获取日线数据"""
        # 转换code为ts_code格式
        if code.startswith('6'):
            ts_code = f"{code}.SH"
        else:
            ts_code = f"{code}.SZ"
        
        query = f"""
            SELECT trade_date as date, ts_code as code, open, high, low, close, 
                   vol as volume, amount
            FROM dwd_daily_price 
            WHERE ts_code = '{ts_code}'
        """
        
        if start_date:
            start_str = str(start_date).replace('/', '-')
            if len(start_str) == 8:
                start_str = f"{start_str[:4]}-{start_str[4:6]}-{start_str[6:8]}"
            query += f" AND trade_date >= '{start_str}'"
        if end_date:
            end_str = str(end_date).replace('/', '-')
            if len(end_str) == 8:
                end_str = f"{end_str[:4]}-{end_str[4:6]}-{end_str[6:8]}"
            query += f" AND trade_date <= '{end_str}'"
        
        query += " ORDER BY trade_date"
        
        df = self.conn.execute(query).fetchdf()
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['date'])
        return df
    
    def get_price_batch(
        self,
        codes: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """批量获取价格数据"""
        def code_to_ts_code(code):
            code = str(code)
            if code.startswith('6'):
                return f"{code}.SH"
            else:
                return f"{code}.SZ"
        
        ts_codes = [code_to_ts_code(c) for c in codes]
        codes_str = "','".join(ts_codes)
        
        query = f"""
            SELECT trade_date as date, ts_code as code, open, high, low, close,
                   vol as volume, amount
            FROM dwd_daily_price 
            WHERE ts_code IN ('{codes_str}')
        """
        
        if start_date:
            query += f" AND trade_date >= '{start_date}'"
        if end_date:
            query += f" AND trade_date <= '{end_date}'"
        
        query += " ORDER BY code, trade_date"
        
        df = self.conn.execute(query).fetchdf()
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['date'])
        return df
    
    # ==================== 多因子数据操作 ====================
    
    def save_factor_data(self, df: pd.DataFrame):
        """保存因子数据"""
        if len(df) == 0:
            return
            
        df = df.copy()
        df['update_time'] = datetime.now()
        
        self.conn.execute("""
            CREATE TEMPORARY TABLE temp_factor AS SELECT * FROM df;
            
            INSERT OR REPLACE INTO factor_data 
            SELECT * FROM temp_factor;
            
            DROP TABLE temp_factor;
        """)
    
    def get_factor_data(
        self,
        date: date,
        factors: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """获取某日的因子数据"""
        if factors:
            factor_cols = ', '.join(factors)
            query = f"""
                SELECT date, code, {factor_cols} 
                FROM factor_data 
                WHERE date = '{date}'
            """
        else:
            query = f"SELECT * FROM factor_data WHERE date = '{date}'"
        
        return self.conn.execute(query).fetchdf()
    
    def get_factor_time_series(
        self,
        code: str,
        factor: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """获取因子时间序列"""
        query = f"""
            SELECT date, code, {factor} 
            FROM factor_data 
            WHERE code = '{code}'
        """
        
        if start_date:
            query += f" AND date >= '{start_date}'"
        if end_date:
            query += f" AND date <= '{end_date}'"
        
        query += " ORDER BY date"
        
        return self.conn.execute(query).fetchdf()
    
    # ==================== 回测结果操作 ====================
    
    def create_backtest_run(
        self,
        strategy_name: str,
        strategy_params: Dict[str, Any],
        start_date: date,
        end_date: date,
        universe: str,
        benchmark: str,
        initial_capital: float
    ) -> str:
        """创建回测记录，返回run_id"""
        import uuid
        run_id = str(uuid.uuid4())[:8]
        
        self.conn.execute(f"""
            INSERT INTO backtest_run 
            (run_id, strategy_name, strategy_params, start_date, end_date, 
             universe, benchmark, initial_capital)
            VALUES 
            ('{run_id}', '{strategy_name}', '{json.dumps(strategy_params)}',
             '{start_date}', '{end_date}', '{universe}', '{benchmark}', {initial_capital})
        """)
        
        return run_id
    
    def save_backtest_trades(self, run_id: str, df: pd.DataFrame):
        """保存回测交易记录"""
        if len(df) == 0:
            return
            
        df = df.copy()
        df['run_id'] = run_id
        
        # 确保datetime列类型正确
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
        
        # 添加自增ID
        existing_count = self.conn.execute(
            f"SELECT COUNT(*) FROM backtest_trades WHERE run_id = '{run_id}'"
        ).fetchone()[0]
        df['id'] = range(existing_count, existing_count + len(df))
        
        # 直接使用INSERT语句插入数据
        for _, row in df.iterrows():
            datetime_val = row['datetime'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['datetime']) else None
            self.conn.execute(f"""
                INSERT INTO backtest_trades 
                (id, run_id, datetime, code, name, action, price, size, amount, commission, industry, market_cap_group)
                VALUES 
                ({row['id']}, '{row.get('run_id', run_id)}', {f"'{datetime_val}'" if datetime_val else "NULL"}, 
                 {f"'{row.get('code')}'" if row.get('code') else "NULL"}, 
                 {f"'{row.get('name')}'" if row.get('name') else "NULL"}, 
                 {f"'{row.get('action')}'" if row.get('action') else "NULL"}, 
                 {row.get('price') if pd.notna(row.get('price')) else "NULL"}, 
                 {row.get('size') if pd.notna(row.get('size')) else "NULL"}, 
                 {row.get('amount') if pd.notna(row.get('amount')) else "NULL"}, 
                 {row.get('commission') if pd.notna(row.get('commission')) else "NULL"}, 
                 {f"'{row.get('industry')}'" if row.get('industry') else "NULL"}, 
                 {f"'{row.get('market_cap_group')}'" if row.get('market_cap_group') else "NULL"})
            """)
    
    def save_backtest_daily_pnl(self, run_id: str, df: pd.DataFrame):
        """保存回测日度盈亏"""
        if len(df) == 0:
            return
            
        df = df.copy()
        df['run_id'] = run_id
        
        # 转换positions列为JSON
        if 'positions' in df.columns:
            df['positions'] = df['positions'].apply(json.dumps)
        
        self.conn.execute("""
            CREATE TEMPORARY TABLE temp_pnl AS SELECT * FROM df;
            
            INSERT OR REPLACE INTO backtest_daily_pnl 
            SELECT * FROM temp_pnl;
            
            DROP TABLE temp_pnl;
        """)
    
    def save_backtest_performance(self, run_id: str, metrics: Dict[str, Any]):
        """保存回测绩效指标"""
        # 转换JSON字段
        json_fields = ['industry_analysis', 'cap_group_analysis', 'monthly_returns']
        for field in json_fields:
            if field in metrics and metrics[field] is not None:
                metrics[field] = json.dumps(metrics[field])
        
        # 构建INSERT语句
        columns = ', '.join(metrics.keys())
        values = []
        for v in metrics.values():
            if isinstance(v, str):
                values.append(f"'{v}'")
            elif v is None:
                values.append("NULL")
            else:
                values.append(str(v))
        values_str = ', '.join(values)
        
        self.conn.execute(f"""
            INSERT OR REPLACE INTO backtest_performance 
            (run_id, {columns})
            VALUES 
            ('{run_id}', {values_str})
        """)
        
        # 更新回测状态为完成
        self.conn.execute(f"""
            UPDATE backtest_run 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE run_id = '{run_id}'
        """)
    
    def get_backtest_result(self, run_id: str) -> Dict[str, pd.DataFrame]:
        """获取完整回测结果"""
        result = {}
        
        # 交易记录
        result['trades'] = self.conn.execute(
            f"SELECT * FROM backtest_trades WHERE run_id = '{run_id}' ORDER BY datetime"
        ).fetchdf()
        
        # 日度盈亏
        result['daily_pnl'] = self.conn.execute(
            f"SELECT * FROM backtest_daily_pnl WHERE run_id = '{run_id}' ORDER BY date"
        ).fetchdf()
        
        # 绩效指标
        result['performance'] = self.conn.execute(
            f"SELECT * FROM backtest_performance WHERE run_id = '{run_id}'"
        ).fetchdf()
        
        return result
    
    # ==================== 多维度分析查询 ====================
    
    def get_industry_performance(self, run_id: str) -> pd.DataFrame:
        """获取分行业绩效"""
        query = f"""
            SELECT 
                industry,
                COUNT(*) as trade_count,
                SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) as win_count,
                AVG(amount) as avg_pnl,
                SUM(amount) as total_pnl
            FROM backtest_trades
            WHERE run_id = '{run_id}'
            GROUP BY industry
            ORDER BY total_pnl DESC
        """
        return self.conn.execute(query).fetchdf()
    
    def get_cap_group_performance(self, run_id: str) -> pd.DataFrame:
        """获取分市值组绩效"""
        query = f"""
            SELECT 
                market_cap_group,
                COUNT(*) as trade_count,
                SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) as win_count,
                AVG(amount) as avg_pnl,
                SUM(amount) as total_pnl
            FROM backtest_trades
            WHERE run_id = '{run_id}'
            GROUP BY market_cap_group
            ORDER BY total_pnl DESC
        """
        return self.conn.execute(query).fetchdf()
    
    def get_trade_calendar(self, start_date: date, end_date: date) -> List[date]:
        """获取交易日历"""
        query = f"""
            SELECT DISTINCT trade_date 
            FROM dwd_daily_price 
            WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
            ORDER BY trade_date
        """
        result = self.conn.execute(query).fetchall()
        return [row[0] for row in result]
    
    # ==================== 数据维护 ====================
    
    def get_last_update_date(self, table: str, code: Optional[str] = None) -> Optional[date]:
        """获取数据最后更新日期"""
        if code:
            query = f"SELECT MAX(date) FROM {table} WHERE code = '{code}'"
        else:
            query = f"SELECT MAX(date) FROM {table}"
        
        result = self.conn.execute(query).fetchone()
        return result[0] if result and result[0] else None
    
    def delete_old_data(self, table: str, before_date: date):
        """删除旧数据"""
        self.conn.execute(f"DELETE FROM {table} WHERE date < '{before_date}'")
        print(f"已删除 {table} 表中 {before_date} 之前的数据")
    
    def vacuum(self):
        """压缩数据库"""
        self.conn.execute("VACUUM")
        print("数据库已压缩")
