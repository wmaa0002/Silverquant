"""
可视化工具 - 图表绘制
"""
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
# 设置后端（必须在导入pyplot之前）
def _setup_backend():
    """设置matplotlib后端"""
    import matplotlib
    import warnings
    
    # 默认使用非交互式后端（兼容服务器/无显示器环境）
    # 用户可以通过设置 MATPLOTLIB_BACKEND 环境变量来覆盖
    backend = os.environ.get('MATPLOTLIB_BACKEND', 'Agg')
    
    # 如果手动指定了其他后端，尝试使用
    if backend != 'Agg':
        try:
            matplotlib.use(backend)
        except Exception:
            matplotlib.use('Agg')
    else:
        matplotlib.use('Agg')

_setup_backend()

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from typing import Optional, List, Tuple, Dict, Any
import seaborn as sns
import duckdb

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimSong', 'Heiti TC', 'Wawati SC', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 数据库路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
ASTOCK3_DB_PATH = PROJECT_ROOT / 'data' / 'Astock3.duckdb'


class ChartPlotter:
    """图表绘制器"""
    
    def __init__(self, figsize: Tuple[int, int] = (12, 6), db_path: Optional[str] = None, show: bool = True):
        """
        初始化
        
        Args:
            figsize: 图表尺寸
            db_path: 数据库路径，默认使用 Astock3.duckdb
            show: 是否显示图表，False时只保存文件
        """
        self.figsize = figsize
        self.style = 'seaborn-v0_8-darkgrid'
        self.db_path = db_path or str(ASTOCK3_DB_PATH)
        self.show = show
    
    def _display_or_save(self, save_path: Optional[str] = None):
        """
        显示或保存图表
        
        Args:
            save_path: 保存路径
        """
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"图表已保存: {save_path}")
        
        if self.show:
            plt.show()
        else:
            plt.close()
    
    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """
        获取数据库连接
        
        Returns:
            duckdb连接对象
        """
        return duckdb.connect(self.db_path)

    def load_backtest_runs(
        self,
        strategy_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> pd.DataFrame:
        """
        加载回测运行记录
        
        Args:
            strategy_name: 策略名称过滤
            status: 状态过滤 (completed, None等)
            limit: 返回数量限制
            
        Returns:
            回测运行记录DataFrame
        """
        conn = self._get_connection()
        
        query = "SELECT * FROM backtest_run WHERE 1=1"
        params = []
        
        if strategy_name:
            query += f" AND strategy_name = ?"
            params.append(strategy_name)
        if status:
            query += f" AND status = ?"
            params.append(status)
        
        query += f" ORDER BY created_at DESC LIMIT {limit}"
        
        df = conn.execute(query, params).df()
        conn.close()
        
        return df

    def load_backtest_trades(
        self,
        run_id: str,
        code: Optional[str] = None,
        action: Optional[str] = None
    ) -> pd.DataFrame:
        """
        加载回测交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码过滤
            action: 交易动作过滤 (BUY/SELL)
            
        Returns:
            交易记录DataFrame
        """
        conn = self._get_connection()
        
        query = "SELECT * FROM backtest_trades WHERE run_id = ?"
        params = [run_id]
        
        if code:
            query += f" AND code = ?"
            params.append(code)
        if action:
            query += f" AND action = ?"
            params.append(action)
        
        query += " ORDER BY datetime"
        
        df = conn.execute(query, params).df()
        conn.close()
        
        return df

    def load_backtest_daily_pnl(self, run_id: str) -> pd.DataFrame:
        """
        加载回测日度盈亏数据
        
        Args:
            run_id: 回测运行ID
            
        Returns:
            日度盈亏DataFrame
        """
        conn = self._get_connection()
        df = conn.execute(
            "SELECT * FROM backtest_daily_pnl WHERE run_id = ? ORDER BY date",
            [run_id]
        ).df()
        conn.close()
        
        return df

    def load_backtest_performance(self, run_id: str) -> Dict[str, Any]:
        """
        加载回测绩效指标
        
        Args:
            run_id: 回测运行ID
            
        Returns:
            绩效指标字典
        """
        conn = self._get_connection()
        
        # 使用 df() 获取带列名的 DataFrame
        df = conn.execute(
            "SELECT * FROM backtest_performance WHERE run_id = ?",
            [run_id]
        ).df()
        
        conn.close()
        
        if df.empty:
            return {}
        
        # 转换为字典
        return df.iloc[0].to_dict()

    def load_backtest_summary(self, run_id: str) -> Dict[str, Any]:
        """
        加载回测汇总信息（运行记录 + 绩效）
        
        Args:
            run_id: 回测运行ID
            
        Returns:
            汇总信息字典
        """
        conn = self._get_connection()
        
        # 加载运行记录
        run_info = conn.execute(
            "SELECT * FROM backtest_run WHERE run_id = ?",
            [run_id]
        ).fetchone()
        
        run_cols = [desc[0] for desc in conn.execute("PRAGMA table_info('backtest_run')").fetchall()]
        run_data = dict(zip(run_cols, run_info)) if run_info else {}
        
        # 加载绩效
        perf_info = conn.execute(
            "SELECT * FROM backtest_performance WHERE run_id = ?",
            [run_id]
        ).fetchone()
        
        perf_cols = [desc[0] for desc in conn.execute("PRAGMA table_info('backtest_performance')").fetchall()]
        perf_data = dict(zip(perf_cols, perf_info)) if perf_info else {}
        
        conn.close()
        
        return {**run_data, **perf_data}

    def load_backtest_summary_by_run_id(self, run_id: str) -> Dict[str, Any]:
        """
        加载回测汇总信息（运行记录 + 绩效）- 简化版
        
        Args:
            run_id: 回测运行ID
            
        Returns:
            汇总信息字典
        """
        # 合并查询
        conn = self._get_connection()
        
        df = conn.execute("""
            SELECT 
                r.run_id,
                r.strategy_name,
                r.strategy_params,
                r.start_date,
                r.end_date,
                r.universe,
                r.benchmark,
                r.initial_capital,
                r.status,
                p.total_return,
                p.annual_return,
                p.max_drawdown,
                p.sharpe_ratio,
                p.win_rate,
                p.total_trades,
                p.avg_holding_days
            FROM backtest_run r
            LEFT JOIN backtest_performance p ON r.run_id = p.run_id
            WHERE r.run_id = ?
        """, [run_id]).df()
        
        conn.close()
        
        if df.empty:
            return {}
        
        return df.iloc[0].to_dict()
    
    def plot_kline(
        self,
        df: pd.DataFrame,
        title: str = 'K线图',
        volume: bool = True,
        ma_periods: List[int] = [5, 10, 20],
        save_path: Optional[str] = None
    ):
        """
        绘制K线图
        
        Args:
            df: 包含OHLCV数据的DataFrame
            title: 图表标题
            volume: 是否显示成交量
            ma_periods: 移动平均线周期
            save_path: 保存路径
        """
        # 创建子图
        if volume:
            fig, (ax1, ax2) = plt.subplots(
                2, 1, 
                figsize=self.figsize,
                gridspec_kw={'height_ratios': [3, 1]},
                sharex=True
            )
        else:
            fig, ax1 = plt.subplots(figsize=self.figsize)
            ax2 = None
        
        # 绘制K线
        for idx, row in df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            # 实体
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            # 影线
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 绘制移动平均线
        for period in ma_periods:
            if f'ma_{period}' in df.columns:
                ax1.plot(df['date'], df[f'ma_{period}'], label=f'MA{period}', alpha=0.7)
        
        ax1.set_title(title)
        ax1.set_ylabel('价格')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        if volume and ax2 is not None:
            colors = ['red' if df.iloc[i]['close'] >= df.iloc[i]['open'] else 'green' 
                     for i in range(len(df))]
            ax2.bar(df['date'], df['volume'], color=colors, alpha=0.7)
            ax2.set_ylabel('成交量')
            ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")
    
    def plot_equity_curve(
        self,
        returns_df: pd.DataFrame,
        benchmark_df: Optional[pd.DataFrame] = None,
        title: str = '权益曲线',
        save_path: Optional[str] = None
    ):
        """
        绘制权益曲线
        
        Args:
            returns_df: 包含策略收益的DataFrame
            benchmark_df: 基准收益DataFrame（可选）
            title: 图表标题
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略收益
        if 'cumulative_return' in returns_df.columns:
            ax.plot(
                returns_df['date'],
                returns_df['cumulative_return'] * 100,
                label='策略',
                linewidth=2
            )
        
        # 绘制基准收益
        if benchmark_df is not None and 'cumulative_return' in benchmark_df.columns:
            ax.plot(
                benchmark_df['date'],
                benchmark_df['cumulative_return'] * 100,
                label='基准',
                linewidth=2,
                alpha=0.7
            )
        
        ax.set_title(title)
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")
    
    def plot_drawdown(
        self,
        returns_df: pd.DataFrame,
        title: str = '回撤曲线',
        save_path: Optional[str] = None
    ):
        """
        绘制回撤曲线
        
        Args:
            returns_df: 包含收益的DataFrame
            title: 图表标题
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        
        if 'drawdown' in returns_df.columns:
            ax.fill_between(
                returns_df['date'],
                returns_df['drawdown'] * 100,
                0,
                color='red',
                alpha=0.3
            )
            ax.plot(
                returns_df['date'],
                returns_df['drawdown'] * 100,
                color='red',
                linewidth=1
            )
        
        ax.set_title(title)
        ax.set_xlabel('日期')
        ax.set_ylabel('回撤 (%)')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")
    
    def plot_monthly_returns_heatmap(
        self,
        returns_df: pd.DataFrame,
        title: str = '月度收益热力图',
        save_path: Optional[str] = None
    ):
        """
        绘制月度收益热力图
        
        Args:
            returns_df: 包含日收益的DataFrame
            title: 图表标题
            save_path: 保存路径
        """
        # 准备数据
        df = returns_df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        
        # 计算月度收益
        monthly = df.groupby(['year', 'month'])['daily_return'].apply(
            lambda x: (1 + x).prod() - 1
        ).reset_index()
        
        # 透视表
        pivot = monthly.pivot(index='year', columns='month', values='daily_return')
        pivot = pivot * 100  # 转换为百分比
        
        # 绘制热力图
        fig, ax = plt.subplots(figsize=(14, 8))
        
        sns.heatmap(
            pivot,
            annot=True,
            fmt='.2f',
            cmap='RdYlGn',
            center=0,
            cbar_kws={'label': '收益率 (%)'},
            ax=ax
        )
        
        ax.set_title(title)
        ax.set_xlabel('月份')
        ax.set_ylabel('年份')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")
    
    def plot_ic_heatmap(
        self,
        ic_df: pd.DataFrame,
        title: str = 'IC热力图',
        save_path: Optional[str] = None
    ):
        """
        绘制IC热力图
        
        Args:
            ic_df: IC值DataFrame，包含date, ic列
            title: 图表标题
            save_path: 保存路径
        """
        # 准备数据
        df = ic_df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        
        # 计算月度平均IC
        monthly_ic = df.groupby(['year', 'month'])['ic'].mean().reset_index()
        
        # 透视表
        pivot = monthly_ic.pivot(index='year', columns='month', values='ic')
        
        # 绘制热力图
        fig, ax = plt.subplots(figsize=(14, 6))
        
        sns.heatmap(
            pivot,
            annot=True,
            fmt='.3f',
            cmap='RdYlGn',
            center=0,
            cbar_kws={'label': 'IC'},
            ax=ax
        )
        
        ax.set_title(title)
        ax.set_xlabel('月份')
        ax.set_ylabel('年份')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")
    
    def plot_factor_distribution(
        self,
        factor_df: pd.DataFrame,
        factor_name: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制因子分布图
        
        Args:
            factor_df: 因子数据DataFrame
            factor_name: 因子名称
            title: 图表标题
            save_path: 保存路径
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # 直方图
        axes[0].hist(factor_df[factor_name].dropna(), bins=50, alpha=0.7, edgecolor='black')
        axes[0].set_xlabel(factor_name)
        axes[0].set_ylabel('频数')
        axes[0].set_title(f'{factor_name} 分布')
        axes[0].grid(True, alpha=0.3)
        
        # 箱线图
        axes[1].boxplot(factor_df[factor_name].dropna())
        axes[1].set_ylabel(factor_name)
        axes[1].set_title(f'{factor_name} 箱线图')
        axes[1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'{factor_name} 分布分析')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")
    
    def plot_correlation_matrix(
        self,
        corr_matrix: pd.DataFrame,
        title: str = '因子相关性矩阵',
        save_path: Optional[str] = None
    ):
        """
        绘制相关性矩阵热力图
        
        Args:
            corr_matrix: 相关性矩阵DataFrame
            title: 图表标题
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=(10, 8))
        
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt='.2f',
            cmap='coolwarm',
            center=0,
            square=True,
            cbar_kws={'label': '相关系数'},
            ax=ax
        )
        
        ax.set_title(title)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")
    
    def plot_quantile_returns(
        self,
        quantile_df: pd.DataFrame,
        title: str = '分位数收益',
        save_path: Optional[str] = None
    ):
        """
        绘制分位数收益图
        
        Args:
            quantile_df: 分位数收益DataFrame
            title: 图表标题
            save_path: 保存路径
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 计算累计收益
        quantile_cols = [col for col in quantile_df.columns if col.startswith('Q')]
        
        for col in quantile_cols:
            cumulative = (1 + quantile_df[col]).cumprod() - 1
            ax.plot(quantile_df.index, cumulative * 100, label=col, linewidth=2)
        
        # 多空收益
        if 'long_short' in quantile_df.columns:
            cumulative_ls = (1 + quantile_df['long_short']).cumprod() - 1
            ax.plot(
                quantile_df.index,
                cumulative_ls * 100,
                label='Long-Short',
                linewidth=2,
                linestyle='--',
                color='black'
            )
        
        ax.set_title(title)
        ax.set_xlabel('日期')
        ax.set_ylabel('累计收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trades_on_price(
        self,
        run_id: str,
        code: str,
        price_df: Optional[pd.DataFrame] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        在K线图上绘制交易记录
        
        Args:
            run_id: 回测运行ID
            code: 股票代码
            price_df: 股票价格数据（需包含date, open, high, low, close列）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id, code=code)
        
        if trades.empty:
            print(f"没有找到股票 {code} 的交易记录")
            return
        
        if price_df is None:
            # 如果没有提供价格数据，只显示交易记录统计
            fig, ax = plt.subplots(figsize=self.figsize)
            ax.set_title(f'{code} 交易记录')
            ax.axis('off')
            
            # 打印交易表格
            table_data = []
            for _, row in trades.iterrows():
                table_data.append([
                    str(row['datetime'])[:19],
                    row['action'],
                    row['code'],
                    row['name'],
                    f"{row['price']:.2f}",
                    row['size'],
                    f"{row['amount']:.2f}"
                ])
            
            table = ax.table(
                cellText=table_data,
                colLabels=['时间', '操作', '代码', '名称', '价格', '数量', '金额'],
                loc='center',
                cellLoc='center'
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1.2, 1.2)
            
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            plt.show()
            return
        
        # 绘制K线图并叠加交易记录
        fig, (ax1, ax2) = plt.subplots(
            2, 1,
            figsize=self.figsize,
            gridspec_kw={'height_ratios': [3, 1]},
            sharex=True
        )
        
        # 绘制K线
        for idx, row in price_df.iterrows():
            color = 'red' if row['close'] >= row['open'] else 'green'
            
            height = abs(row['close'] - row['open'])
            bottom = min(row['close'], row['open'])
            rect = Rectangle(
                (mdates.date2num(row['date']) - 0.3, bottom),
                0.6, height,
                facecolor=color,
                edgecolor=color
            )
            ax1.add_patch(rect)
            
            ax1.plot(
                [mdates.date2num(row['date']), mdates.date2num(row['date'])],
                [row['low'], row['high']],
                color=color,
                linewidth=1
            )
        
        # 标记买入点
        buy_trades = trades[trades['action'] == 'BUY']
        for _, row in buy_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='red',
                marker='^',
                s=200,
                zorder=5,
                label='买入' if _ == 0 else ''
            )
        
        # 标记卖出点
        sell_trades = trades[trades['action'] == 'SELL']
        for _, row in sell_trades.iterrows():
            trade_date = pd.to_datetime(row['datetime']).date()
            ax1.scatter(
                mdates.date2num(trade_date),
                row['price'],
                color='green',
                marker='v',
                s=200,
                zorder=5,
                label='卖出' if _ == 0 else ''
            )
        
        ax1.set_title(title or f'{code} 交易记录')
        ax1.set_ylabel('价格')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 绘制成交量
        colors = ['red' if price_df.iloc[i]['close'] >= price_df.iloc[i]['open'] else 'green'
                 for i in range(len(price_df))]
        ax2.bar(price_df['date'], price_df['volume'], color=colors, alpha=0.7)
        ax2.set_ylabel('成交量')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_equity_curve(
        self,
        run_id: str,
        benchmark_code: Optional[str] = None,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测权益曲线
        
        Args:
            run_id: 回测运行ID
            benchmark_code: 基准股票代码（如 '000001' 上证指数）
            title: 图表标题
            save_path: 保存路径
        """
        # 加载日度盈亏
        daily_pnl = self.load_backtest_daily_pnl(run_id)
        
        if daily_pnl.empty:
            print(f"没有找到回测 {run_id} 的日度盈亏数据")
            return
        
        # 计算累计收益
        daily_pnl['cumulative_pnl'] = daily_pnl['pnl'].cumsum()
        daily_pnl['total_value_normalized'] = daily_pnl['total_value'] / daily_pnl['total_value'].iloc[0]
        
        fig, ax = plt.subplots(figsize=self.figsize)
        
        # 绘制策略权益
        ax.plot(
            daily_pnl['date'],
            daily_pnl['total_value_normalized'] * 100 - 100,
            label='策略',
            linewidth=2,
            color='blue'
        )
        
        # 绘制基准收益（如果有）
        if benchmark_code:
            # TODO: 加载基准数据
            pass
        
        ax.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        ax.set_title(title or '权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('收益率 (%)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_performance(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制回测绩效指标
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载绩效数据
        perf = self.load_backtest_performance(run_id)
        
        if not perf:
            print(f"没有找到回测 {run_id} 的绩效数据")
            return
        
        # 提取关键指标
        metrics = {
            '总收益率': f"{perf.get('total_return', 0) * 100:.2f}%",
            '年化收益率': f"{perf.get('annual_return', 0) * 100:.2f}%",
            '最大回撤': f"{perf.get('max_drawdown', 0):.2f}%",
            '夏普比率': f"{perf.get('sharpe_ratio', 0):.2f}",
            '胜率': f"{perf.get('win_rate', 0) * 100:.2f}%",
            '总交易次数': str(perf.get('total_trades', 0)),
            '平均持仓天数': f"{perf.get('avg_holding_days', 0):.1f}"
        }
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        # 创建表格
        table_data = [[k, v] for k, v in metrics.items()]
        table = ax.table(
            cellText=table_data,
            colLabels=['指标', '值'],
            loc='center',
            cellLoc='center',
            colWidths=[0.4, 0.3]
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        # 设置表头样式
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title(title or '回测绩效指标', fontsize=14, pad=20)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_trade_statistics(
        self,
        run_id: str,
        title: Optional[str] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制交易统计图表
        
        Args:
            run_id: 回测运行ID
            title: 图表标题
            save_path: 保存路径
        """
        # 加载交易记录
        trades = self.load_backtest_trades(run_id)
        
        if trades.empty:
            print(f"没有找到回测 {run_id} 的交易记录")
            return
        
        # 分离买卖
        buys = trades[trades['action'] == 'BUY']
        sells = trades[trades['action'] == 'SELL']
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 每月交易次数
        trades['month'] = pd.to_datetime(trades['datetime']).dt.to_period('M')
        monthly_trades = trades.groupby('month').size()
        
        axes[0, 0].bar(range(len(monthly_trades)), monthly_trades.values, alpha=0.7)
        axes[0, 0].set_xticks(range(len(monthly_trades)))
        axes[0, 0].set_xticklabels([str(m) for m in monthly_trades.index], rotation=45)
        axes[0, 0].set_title('每月交易次数')
        axes[0, 0].set_ylabel('交易次数')
        axes[0, 0].grid(True, alpha=0.3)
        
        # 2. 买入/卖出分布
        action_counts = trades['action'].value_counts()
        axes[0, 1].pie(
            action_counts.values,
            labels=action_counts.index,
            autopct='%1.1f%%',
            colors=['red', 'green'][:len(action_counts)],
            startangle=90
        )
        axes[0, 1].set_title('买入/卖出分布')
        
        # 3. 行业分布
        if 'industry' in trades.columns and trades['industry'].notna().any():
            industry_counts = trades['industry'].value_counts().head(10)
            axes[1, 0].barh(range(len(industry_counts)), industry_counts.values, alpha=0.7)
            axes[1, 0].set_yticks(range(len(industry_counts)))
            axes[1, 0].set_yticklabels(industry_counts.index)
            axes[1, 0].set_title('行业分布 (Top 10)')
            axes[1, 0].set_xlabel('交易次数')
            axes[1, 0].grid(True, alpha=0.3)
        else:
            axes[1, 0].text(0.5, 0.5, '无行业数据', ha='center', va='center')
            axes[1, 0].set_title('行业分布')
        
        # 4. 股票分布
        stock_counts = trades['code'].value_counts().head(10)
        axes[1, 1].barh(range(len(stock_counts)), stock_counts.values, alpha=0.7)
        axes[1, 1].set_yticks(range(len(stock_counts)))
        axes[1, 1].set_yticklabels(stock_counts.index)
        axes[1, 1].set_title('股票分布 (Top 10)')
        axes[1, 1].set_xlabel('交易次数')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.suptitle(title or f'交易统计 - {run_id}', fontsize=14)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        plt.show()

    def plot_backtest_full_report(
        self,
        run_id: str,
        price_data: Optional[Dict[str, pd.DataFrame]] = None,
        save_dir: Optional[str] = None
    ):
        """
        生成完整的回测报告
        
        Args:
            run_id: 回测运行ID
            price_data: 股票价格数据字典 {code: DataFrame}
            save_dir: 保存目录
        """
        # 加载汇总信息
        summary = self.load_backtest_summary(run_id)
        
        if not summary:
            print(f"没有找到回测 {run_id} 的数据")
            return
        
        print(f"\n{'='*50}")
        print(f"回测报告 - {run_id}")
        print(f"{'='*50}")
        print(f"策略: {summary.get('strategy_name', 'N/A')}")
        print(f"回测期间: {summary.get('start_date', 'N/A')} ~ {summary.get('end_date', 'N/A')}")
        print(f"初始资金: {summary.get('initial_capital', 'N/A')}")
        print(f"{'='*50}\n")
        
        # 绘制绩效指标
        print("绘制绩效指标...")
        self.plot_backtest_performance(
            run_id,
            title=f"绩效指标 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/performance.png" if save_dir else None
        )
        
        # 绘制权益曲线
        print("绘制权益曲线...")
        self.plot_backtest_equity_curve(
            run_id,
            title=f"权益曲线 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/equity_curve.png" if save_dir else None
        )
        
        # 绘制交易统计
        print("绘制交易统计...")
        self.plot_trade_statistics(
            run_id,
            title=f"交易统计 - {summary.get('strategy_name', '')}",
            save_path=f"{save_dir}/trade_stats.png" if save_dir else None
        )
        
        # 绘制各股票的交易
        trades = self.load_backtest_trades(run_id)
        if not trades.empty and price_data:
            codes = trades['code'].unique()
            print(f"绘制 {len(codes)} 只股票的交易记录...")
            for code in codes:
                if code in price_data:
                    self.plot_trades_on_price(
                        run_id,
                        code,
                        price_data[code],
                        save_path=f"{save_dir}/trades_{code}.png" if save_dir else None
                    )
        
        print("\n报告生成完成!")

        print("\n报告生成完成!")

    def plot_batch_summary(self, results_df: pd.DataFrame, save_dir: str = None):
        """绘制批量回测汇总图表"""
        if save_dir is None:
            save_dir = "."
        
        os.makedirs(save_dir, exist_ok=True)
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        returns = results_df['total_return'] * 100
        ax1 = axes[0, 0]
        ax1.hist(returns, bins=50, edgecolor='black', alpha=0.7, color='#3498db')
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
        ax1.axvline(x=returns.mean(), color='green', linestyle='--', linewidth=2, label=f'均值: {returns.mean():.2f}%')
        ax1.set_xlabel('收益率 (%)')
        ax1.set_ylabel('数量')
        ax1.set_title('收益率分布')
        ax1.legend()
        
        ax2 = axes[0, 1]
        positive = len(results_df[results_df['total_return']>0])
        negative = len(results_df[results_df['total_return']<0])
        zero = len(results_df[results_df['total_return']==0])
        sizes = [positive, negative, zero]
        labels = [f'盈利 ({positive})', f'亏损 ({negative})', f'持平 ({zero})']
        colors = ['#2ecc71', '#e74c3c', '#95a5a6']
        ax2.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax2.set_title('收益分类')
        
        ax3 = axes[1, 0]
        top10 = results_df.nlargest(10, 'total_return')
        codes = [str(row['code']) for _, row in top10.iterrows()]
        values = [row['total_return']*100 for _, row in top10.iterrows()]
        ax3.barh(range(len(codes)), values, color='#e74c3c')
        ax3.set_yticks(range(len(codes)))
        ax3.set_yticklabels(codes)
        ax3.set_xlabel('收益率 (%)')
        ax3.set_title('收益Top10')
        ax3.invert_yaxis()
        
        ax4 = axes[1, 1]
        trade_counts = results_df['total_trades'].value_counts().sort_index()
        ax4.bar(trade_counts.index, trade_counts.values, color='#9b59b6')
        ax4.set_xlabel('交易次数')
        ax4.set_ylabel('数量')
        ax4.set_title('交易次数分布')
        
        plt.suptitle(f'批量回测汇总 - {len(results_df)}只股票', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig(f"{save_dir}/batch_summary.png", dpi=150, bbox_inches='tight')
        self._display_or_save(save_path=f"{save_dir}/batch_summary.png")
        
        fig2, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        
        summary_data = [
            ['股票总数', str(len(results_df))],
            ['平均收益率', f"{results_df['total_return'].mean()*100:.2f}%"],
            ['中位数收益率', f"{results_df['total_return'].median()*100:.2f}%"],
            ['最大收益率', f"{results_df['total_return'].max()*100:.2f}%"],
            ['最小收益率', f"{results_df['total_return'].min()*100:.2f}%"],
            ['盈利股票', f"{positive} ({positive/len(results_df)*100:.1f}%)"],
            ['亏损股票', f"{negative} ({negative/len(results_df)*100:.1f}%)"],
            ['总交易次数', f"{int(results_df['total_trades'].sum())}"],
        ]
        
        table = ax.table(cellText=summary_data, colLabels=['指标', '值'], loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.5, 2)
        
        for i in range(2):
            table[(0, i)].set_facecolor('#4472C4')
            table[(0, i)].set_text_props(color='white', weight='bold')
        
        ax.set_title('批量回测统计', fontsize=14, pad=20)
        plt.tight_layout()
        plt.savefig(f"{save_dir}/batch_statistics.png", dpi=150, bbox_inches='tight')
        self._display_or_save(save_path=f"{save_dir}/batch_statistics.png")