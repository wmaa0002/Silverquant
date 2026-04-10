"""
基本面分析师 - FundamentalsAnalyst实现
"""
from typing import Dict, Any, List, Optional

from agent_integration.agents.base import BaseAgent, AgentConfig


class FundamentalsAnalyst(BaseAgent):
    """基本面分析师智能体
    
    负责分析公司财务报表、估值指标和基本面数据。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化基本面分析师"""
        super().__init__(config)
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是A股市场基本面分析师，专注于分析公司的财务状况、估值水平和成长性。

你的职责：
1. 分析公司盈利能力（毛利率、净利率、ROE等）
2. 评估公司估值水平（P/E、P/B、PEG等）
3. 分析公司成长性（营收增长、利润增长等）
4. 评估公司财务健康状况（负债率、现金流等）
5. 与行业平均水平对比

分析要求：
- 基于客观财务数据
- 结合行业特性分析
- 关注长期趋势而非单期数据
- 提示投资价值和潜在风险

请用简洁专业的语言输出分析结果。"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """处理输入数据"""
        task = inputs.get('task', 'analyze')
        stock_code = inputs.get('stock_code', '')
        
        if task == 'analyze_financials':
            financial_data = inputs.get('financial_data', {})
            return self._format_financials(stock_code, financial_data)
        
        elif task == 'analyze_valuation':
            valuation_data = inputs.get('valuation_data', {})
            return self._format_valuation(stock_code, valuation_data)
        
        elif task == 'analyze_growth':
            growth_data = inputs.get('growth_data', {})
            return self._format_growth(stock_code, growth_data)
        
        # 默认：处理所有数据
        financial_data = inputs.get('financial_data', {})
        valuation_data = inputs.get('valuation_data', {})
        growth_data = inputs.get('growth_data', {})
        
        parts = [f"股票代码: {stock_code}\n"]
        
        if financial_data:
            parts.append("【财务数据】\n")
            parts.append(self._format_financials(stock_code, financial_data))
            parts.append("\n")
        
        if valuation_data:
            parts.append("【估值数据】\n")
            parts.append(self._format_valuation(stock_code, valuation_data))
            parts.append("\n")
        
        if growth_data:
            parts.append("【成长数据】\n")
            parts.append(self._format_growth(stock_code, growth_data))
        
        parts.append("\n请分析以上基本面数据，给出投资建议。")
        
        return "\n".join(parts)
    
    def _format_financials(self, stock_code: str, financial_data: Dict) -> str:
        """格式化财务数据"""
        lines = [f"股票代码: {stock_code}\n"]
        
        if not financial_data:
            lines.append("无财务数据")
            return "\n".join(lines)
        
        # 盈利能力
        if 'profitability' in financial_data:
            lines.append("盈利能力:")
            prof = financial_data['profitability']
            for key, value in prof.items():
                if value is not None and str(value) != 'None':
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        # 财务指标
        common_fields = [
            ('revenue', '营业收入'),
            ('net_profit', '净利润'),
            ('total_assets', '总资产'),
            ('total_liabilities', '总负债'),
            ('equity', '净资产'),
            ('gross_margin', '毛利率'),
            ('net_margin', '净利率'),
            ('roe', 'ROE'),
            ('roa', 'ROA'),
        ]
        
        has_data = False
        for field, name in common_fields:
            if field in financial_data:
                value = financial_data[field]
                lines.append(f"{name}: {value}")
                has_data = True
        
        if has_data:
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_valuation(self, stock_code: str, valuation_data: Dict) -> str:
        """格式化估值数据"""
        lines = [f"股票代码: {stock_code}\n"]
        
        if not valuation_data:
            lines.append("无估值数据")
            return "\n".join(lines)
        
        valuation_fields = [
            ('pe', '市盈率P/E'),
            ('pb', '市净率P/B'),
            ('ps', '市销率P/S'),
            ('pcf', '现金流倍率'),
            ('peg', 'PEG'),
            ('market_cap', '总市值'),
            ('circulating_market_cap', '流通市值'),
            ('enterprise_value', '企业价值EV'),
        ]
        
        for field, name in valuation_fields:
            if field in valuation_data:
                value = valuation_data[field]
                lines.append(f"{name}: {value}")
        
        lines.append("")
        return "\n".join(lines)
    
    def _format_growth(self, stock_code: str, growth_data: Dict) -> str:
        """格式化成长数据"""
        lines = [f"股票代码: {stock_code}\n"]
        
        if not growth_data:
            lines.append("无成长数据")
            return "\n".join(lines)
        
        growth_fields = [
            ('revenue_growth', '营收增长率'),
            ('profit_growth', '利润增长率'),
            ('asset_growth', '资产增长率'),
            ('equity_growth', '净资产增长率'),
            ('quarterly_revenue', '季度营收'),
            ('quarterly_profit', '季度利润'),
            ('yoy_growth', '同比增长'),
            ('qoq_growth', '环比增长'),
        ]
        
        for field, name in growth_fields:
            if field in growth_data:
                value = growth_data[field]
                lines.append(f"{name}: {value}")
        
        lines.append("")
        return "\n".join(lines)
    
    def analyze_financials(self, stock_code: str, financial_data: Dict = None) -> Dict[str, Any]:
        """分析财务数据
        
        Args:
            stock_code: 股票代码
            financial_data: 财务数据
            
        Returns:
            财务分析结果
        """
        return self.run({
            'task': 'analyze_financials',
            'stock_code': stock_code,
            'financial_data': financial_data or {}
        })
    
    def analyze_valuation(self, stock_code: str, valuation_data: Dict = None) -> Dict[str, Any]:
        """分析估值水平
        
        Args:
            stock_code: 股票代码
            valuation_data: 估值数据
            
        Returns:
            估值分析结果
        """
        return self.run({
            'task': 'analyze_valuation',
            'stock_code': stock_code,
            'valuation_data': valuation_data or {}
        })
    
    def analyze_growth(self, stock_code: str, growth_data: Dict = None) -> Dict[str, Any]:
        """分析成长性
        
        Args:
            stock_code: 股票代码
            growth_data: 成长数据
            
        Returns:
            成长性分析结果
        """
        return self.run({
            'task': 'analyze_growth',
            'stock_code': stock_code,
            'growth_data': growth_data or {}
        })
    
    def analyze_all(self, stock_code: str, financial_data: Dict = None,
                   valuation_data: Dict = None, growth_data: Dict = None) -> Dict[str, Any]:
        """综合基本面分析
        
        Args:
            stock_code: 股票代码
            financial_data: 财务数据
            valuation_data: 估值数据
            growth_data: 成长数据
            
        Returns:
            综合分析结果
        """
        return self.run({
            'stock_code': stock_code,
            'financial_data': financial_data or {},
            'valuation_data': valuation_data or {},
            'growth_data': growth_data or {}
        })