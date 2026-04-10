"""
市场分析师 - MarketAnalyst实现
"""
from typing import Dict, Any, List, Optional
import pandas as pd

from agent_integration.agents.base import BaseAgent, AgentConfig


class MarketAnalyst(BaseAgent):
    """市场分析师智能体
    
    负责分析市场走势、价格模式和交易量。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化市场分析师"""
        super().__init__(config)
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是A股市场技术分析师，专注于分析股票的价格走势、技术指标和市场趋势。

你的职责：
1. 分析K线形态和价格模式
2. 解读技术指标（MA、MACD、RSI、KDJ等）
3. 判断市场趋势（上涨、下跌、横盘）
4. 识别支撑位和压力位
5. 给出交易建议（买入、卖出、持有）

分析要求：
- 结合量价关系分析
- 注意技术指标的背离信号
- 结合市场整体环境判断
- 客观呈现多空观点

请用简洁专业的语言输出分析结果。"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """处理输入数据"""
        stock_code = inputs.get('stock_code', '')
        price_data = inputs.get('price_data')
        indicators = inputs.get('indicators', {})
        
        parts = [f"股票代码: {stock_code}\n"]
        
        if price_data is not None:
            parts.append("【K线数据】\n")
            parts.append(self._format_price_data(price_data))
            parts.append("\n")
        
        if indicators:
            parts.append("【技术指标】\n")
            parts.append(self._format_indicators(indicators))
        
        parts.append("\n请分析以上数据，给出技术分析结论。")
        
        return "\n".join(parts)
    
    def _format_price_data(self, data) -> str:
        """格式化OHLCV数据为文本表格
        
        Args:
            data: 价格数据 (DataFrame或dict)
            
        Returns:
            格式化的文本表格
        """
        if data is None:
            return "无数据"
        
        if isinstance(data, pd.DataFrame):
            if len(data) == 0:
                return "无数据"
            
            # 取最近20条数据
            df = data.tail(20).copy()
            
            lines = []
            lines.append(f"{'日期':<12} {'开盘':>10} {'最高':>10} {'最低':>10} {'收盘':>10} {'成交量':>12} {'涨跌幅':>10}")
            lines.append("-" * 80)
            
            for _, row in df.iterrows():
                date_str = str(row.get('date', ''))[:10]
                open_p = row.get('open', 0)
                high_p = row.get('high', 0)
                low_p = row.get('low', 0)
                close_p = row.get('close', 0)
                volume = row.get('volume', 0)
                pct = row.get('pct_change', row.get('pct_chg', 0))
                
                lines.append(
                    f"{date_str:<12} "
                    f"{open_p:>10.2f} "
                    f"{high_p:>10.2f} "
                    f"{low_p:>10.2f} "
                    f"{close_p:>10.2f} "
                    f"{volume:>12.0f} "
                    f"{pct:>9.2f}%"
                )
            
            return "\n".join(lines)
        
        if isinstance(data, dict):
            return self._format_price_dict(data)
        
        return str(data)
    
    def _format_price_dict(self, data: Dict) -> str:
        """格式化单个价格数据字典"""
        date = data.get('date', '')
        open_p = data.get('open', 0)
        high = data.get('high', 0)
        low = data.get('low', 0)
        close = data.get('close', 0)
        volume = data.get('volume', 0)
        pct = data.get('pct_change', 0)
        
        return f"""日期: {date}
开盘: {open_p:.2f}  最高: {high:.2f}  最低: {low:.2f}  收盘: {close:.2f}
成交量: {volume:.0f}  涨跌幅: {pct:.2f}%"""
    
    def _format_indicators(self, indicators: Dict[str, Any]) -> str:
        """格式化技术指标
        
        Args:
            indicators: 技术指标字典
            
        Returns:
            格式化后的指标字符串
        """
        if not indicators:
            return "无指标数据"
        
        lines = []
        
        # MA指标
        if 'ma' in indicators:
            ma = indicators['ma']
            if isinstance(ma, dict):
                ma_lines = [f"MA{k}: {v:.2f}" for k, v in ma.items()]
                lines.append(f"均线: {', '.join(ma_lines)}")
            else:
                lines.append(f"均线: {ma}")
        
        # MACD
        if 'macd' in indicators:
            macd = indicators['macd']
            if isinstance(macd, dict):
                dif = macd.get('dif', macd.get('DIF', 0))
                dea = macd.get('dea', macd.get('DEA', 0))
                hist = macd.get('hist', macd.get('HIST', 0))
                lines.append(f"MACD: DIF={dif:.4f}, DEA={dea:.4f}, HIST={hist:.4f}")
            else:
                lines.append(f"MACD: {macd}")
        
        # RSI
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            if isinstance(rsi, dict):
                rsi_lines = [f"RSI{k}: {v:.2f}" for k, v in rsi.items()]
                lines.append(", ".join(rsi_lines))
            else:
                lines.append(f"RSI: {rsi:.2f}")
        
        # KDJ
        if 'kdj' in indicators:
            kdj = indicators['kdj']
            if isinstance(kdj, dict):
                k = kdj.get('k', kdj.get('K', 0))
                d = kdj.get('d', kdj.get('D', 0))
                j = kdj.get('j', kdj.get('J', 0))
                lines.append(f"KDJ: K={k:.2f}, D={d:.2f}, J={j:.2f}")
            else:
                lines.append(f"KDJ: {kdj}")
        
        # BOLL
        if 'boll' in indicators:
            boll = indicators['boll']
            if isinstance(boll, dict):
                upper = boll.get('upper', 0)
                middle = boll.get('middle', boll.get('mid', 0))
                lower = boll.get('lower', 0)
                lines.append(f"BOLL: 上轨={upper:.2f}, 中轨={middle:.2f}, 下轨={lower:.2f}")
            else:
                lines.append(f"BOLL: {boll}")
        
        # 成交量
        if 'volume' in indicators:
            vol = indicators['volume']
            lines.append(f"成交量: {vol}")
        
        if not lines:
            return str(indicators)
        
        return "\n".join(lines)
    
    def analyze_trend(self, stock_code: str, period: str = '1d') -> Dict[str, Any]:
        """分析股票趋势
        
        Args:
            stock_code: 股票代码
            period: 时间周期
            
        Returns:
            趋势分析结果
        """
        result = self.run({
            'stock_code': stock_code,
            'period': period,
            'task': 'analyze_trend'
        })
        return result
    
    def analyze_volume(self, stock_code: str) -> Dict[str, Any]:
        """分析交易量
        
        Args:
            stock_code: 股票代码
            
        Returns:
            交易量分析结果
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'analyze_volume'
        })
        return result
    
    def analyze_pattern(self, stock_code: str) -> Dict[str, Any]:
        """识别价格形态
        
        Args:
            stock_code: 股票代码
            
        Returns:
            形态识别结果
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'analyze_pattern'
        })
        return result
    
    def analyze_with_data(self, stock_code: str, price_data, indicators: Dict = None) -> Dict[str, Any]:
        """使用数据进行分析
        
        Args:
            stock_code: 股票代码
            price_data: K线数据
            indicators: 技术指标
            
        Returns:
            分析结果
        """
        return self.run({
            'stock_code': stock_code,
            'price_data': price_data,
            'indicators': indicators or {}
        })