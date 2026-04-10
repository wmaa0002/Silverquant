"""
牛市研究员 - BullResearcher实现
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from agent_integration.agents.base import BaseAgent, AgentConfig


class BullResearcher(BaseAgent):
    """牛市/做多研究员智能体
    
    负责收集支持做多的论据和信号。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化牛市研究员"""
        super().__init__(config)
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是A股市场牛市/做多研究员，专注于寻找支持做多的投资论点。

你的职责：
1. 分析股票的上涨催化剂和驱动因素
2. 识别技术面的看涨信号
3. 发现基本面的利好因素
4. 评估市场情绪转向积极的信号
5. 给出目标价位和上涨空间

做多论据类型：
- 业绩超预期
- 行业景气度提升
- 政策利好
- 技术面突破
- 资金流入
- 估值修复
- 市场占有率提升

输出要求：
1. 列出3-5个支持做多的具体论据
2. 每个论据要有数据支撑
3. 给出目标价和预期涨幅
4. 标注置信度

请用专业简洁的语言输出。"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """处理输入数据"""
        stock_code = inputs.get('stock_code', '')
        market_report = inputs.get('market_report', '')
        news_report = inputs.get('news_report', '')
        fundamentals_report = inputs.get('fundamentals_report', '')
        
        parts = [f"股票代码: {stock_code}\n"]
        
        if inputs.get('trade_date'):
            parts.append(f"交易日期: {inputs.get('trade_date')}\n")
        
        if market_report:
            parts.append("【技术分析报告】\n")
            parts.append(market_report)
            parts.append("\n\n")
        
        if news_report:
            parts.append("【新闻分析报告】\n")
            parts.append(news_report)
            parts.append("\n\n")
        
        if fundamentals_report:
            parts.append("【基本面分析报告】\n")
            parts.append(fundamentals_report)
            parts.append("\n\n")
        
        parts.append("请基于以上分析报告，找出支持做多的论据和信号。")
        
        return "\n".join(parts)
    
    def research_bull_case(self, stock_code: str) -> Dict[str, Any]:
        """研究做多理由
        
        Args:
            stock_code: 股票代码
            
        Returns:
            做多研究结果 {
                'bull_points': [...],
                'target_price': float,
                'upside_potential': float,
                'confidence': float
            }
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'bull_case'
        })
        
        if result['success']:
            return self._parse_bull_result(result['output'])
        return {
            'bull_points': [],
            'target_price': 0.0,
            'upside_potential': 0.0,
            'confidence': 0.0,
            'error': result.get('error', 'Unknown error')
        }
    
    def _parse_bull_result(self, output: str) -> Dict[str, Any]:
        """解析LLM输出的做多结果"""
        result = {
            'bull_points': [],
            'target_price': 0.0,
            'upside_potential': 0.0,
            'confidence': 0.5,
            'raw_output': output
        }
        
        lines = output.split('\n')
        for line in lines:
            line_lower = line.lower()
            if '目标价' in line or 'target price' in line_lower:
                try:
                    import re
                    nums = re.findall(r'\d+\.?\d*', line)
                    if nums:
                        result['target_price'] = float(nums[0])
                except:
                    pass
            elif '上涨' in line and '%' in line:
                try:
                    import re
                    nums = re.findall(r'(\d+\.?\d*)%', line)
                    if nums:
                        result['upside_potential'] = float(nums[0])
                except:
                    pass
            elif '置信度' in line or 'confidence' in line_lower:
                try:
                    import re
                    nums = re.findall(r'0?\.\d+', line)
                    if nums:
                        result['confidence'] = float(nums[0])
                except:
                    pass
        
        return result
    
    def find_supporting_signals(self, stock_code: str) -> List[Dict[str, Any]]:
        """寻找支撑信号
        
        Args:
            stock_code: 股票代码
            
        Returns:
            支撑信号列表 [{
                'signal': str,
                'description': str,
                'strength': str  # 'strong', 'medium', 'weak'
            }]
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'supporting_signals'
        })
        
        if result['success']:
            return self._parse_signals(result['output'], bullish=True)
        return []
    
    def find_bullish_patterns(self, stock_code: str) -> List[str]:
        """识别看涨形态
        
        Args:
            stock_code: 股票代码
            
        Returns:
            看涨形态列表
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'bullish_patterns'
        })
        
        if result['success']:
            patterns = []
            for line in result['output'].split('\n'):
                if line.strip() and len(line.strip()) > 2:
                    patterns.append(line.strip())
            return patterns[:5]
        return []
    
    def _parse_signals(self, output: str, bullish: bool = True) -> List[Dict[str, Any]]:
        """解析信号列表"""
        signals = []
        signal_type = 'bullish' if bullish else 'bearish'
        
        lines = output.split('\n')
        current_signal = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if any(kw in line for kw in ['信号', 'signal', '利好', '利空']):
                current_signal = {'signal': line, 'description': '', 'strength': 'medium'}
            elif current_signal and current_signal['description']:
                current_signal['description'] += ' ' + line
            elif current_signal:
                current_signal['description'] = line
            
            if current_signal and current_signal['description']:
                if len(current_signal['description']) > 20:
                    signals.append(current_signal)
                    current_signal = None
        
        if current_signal and current_signal['description']:
            signals.append(current_signal)
        
        return signals[:5]
    
    def research_with_reports(self, stock_code: str, trade_date: str,
                            market_report: str = '',
                            news_report: str = '',
                            fundamentals_report: str = '') -> Dict[str, Any]:
        """基于分析报告研究做多论点
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            market_report: 技术分析报告
            news_report: 新闻分析报告
            fundamentals_report: 基本面分析报告
            
        Returns:
            做多研究结果
        """
        result = self.run({
            'stock_code': stock_code,
            'trade_date': trade_date,
            'market_report': market_report,
            'news_report': news_report,
            'fundamentals_report': fundamentals_report,
            'task': 'bull_case'
        })
        
        if result['success']:
            parsed = self._parse_bull_result(result['output'])
            parsed['research_output'] = result['output']
            return parsed
        
        return {
            'bull_points': [],
            'target_price': 0.0,
            'upside_potential': 0.0,
            'confidence': 0.0,
            'error': result.get('error', 'Unknown error')
        }