"""
熊市研究员 - BearResearcher实现
"""
from typing import Dict, Any, List
from datetime import datetime

from agent_integration.agents.base import BaseAgent, AgentConfig


class BearResearcher(BaseAgent):
    """熊市/做空研究员智能体
    
    负责收集支持做空/回避的论据和风险信号。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化熊市研究员"""
        super().__init__(config)
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是A股市场熊市/风险研究员，专注于识别投资风险和做空/回避理由。

你的职责：
1. 识别股票的下跌风险和驱动因素
2. 发现技术面的看跌信号
3. 揭示基本面的利空因素
4. 评估市场情绪转向消极的信号
5. 给出风险水平和下跌空间

风险论据类型：
- 业绩低于预期
- 行业景气度下降
- 政策利空
- 技术面破位
- 资金流出
- 估值过高
- 市场份额下降
- 竞争加剧

输出要求：
1. 列出3-5个支持回避/做空的论据
2. 每个论据要有风险数据支撑
3. 给出风险水平和下跌空间
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
        
        parts.append("请基于以上分析报告，找出风险信号和回避/做空理由。")
        
        return "\n".join(parts)
    
    def research_bear_case(self, stock_code: str) -> Dict[str, Any]:
        """研究做空/回避理由
        
        Args:
            stock_code: 股票代码
            
        Returns:
            做空研究结果 {
                'bear_points': [...],
                'risk_level': str,
                'downside_risk': float,
                'confidence': float
            }
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'bear_case'
        })
        
        if result['success']:
            return self._parse_bear_result(result['output'])
        return {
            'bear_points': [],
            'risk_level': 'unknown',
            'downside_risk': 0.0,
            'confidence': 0.5,
            'error': result.get('error', 'Unknown error')
        }
    
    def _parse_bear_result(self, output: str) -> Dict[str, Any]:
        """解析LLM输出的做空结果"""
        result = {
            'bear_points': [],
            'risk_level': 'medium',
            'downside_risk': 0.0,
            'confidence': 0.5,
            'raw_output': output
        }
        
        lines = output.split('\n')
        for line in lines:
            line_lower = line.lower()
            if '风险' in line and '等级' in line:
                if '高' in line or 'high' in line_lower:
                    result['risk_level'] = 'high'
                elif '低' in line or 'low' in line_lower:
                    result['risk_level'] = 'low'
            elif '下跌' in line and '%' in line:
                try:
                    import re
                    nums = re.findall(r'(\d+\.?\d*)%', line)
                    if nums:
                        result['downside_risk'] = float(nums[0])
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
    
    def find_risk_signals(self, stock_code: str) -> List[Dict[str, Any]]:
        """寻找风险信号
        
        Args:
            stock_code: 股票代码
            
        Returns:
            风险信号列表 [{
                'signal': str,
                'description': str,
                'severity': str  # 'high', 'medium', 'low'
            }]
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'risk_signals'
        })
        
        if result['success']:
            return self._parse_signals(result['output'])
        return []
    
    def find_bearish_patterns(self, stock_code: str) -> List[str]:
        """识别看跌形态
        
        Args:
            stock_code: 股票代码
            
        Returns:
            看跌形态列表
        """
        result = self.run({
            'stock_code': stock_code,
            'task': 'bearish_patterns'
        })
        
        if result['success']:
            patterns = []
            for line in result['output'].split('\n'):
                if line.strip() and len(line.strip()) > 2:
                    patterns.append(line.strip())
            return patterns[:5]
        return []
    
    def _parse_signals(self, output: str) -> List[Dict[str, Any]]:
        """解析信号列表"""
        signals = []
        
        lines = output.split('\n')
        current_signal = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if any(kw in line for kw in ['风险', 'risk', '警示', '警告']):
                current_signal = {'signal': line, 'description': '', 'severity': 'medium'}
            elif current_signal and current_signal['description']:
                current_signal['description'] += ' ' + line
            elif current_signal:
                current_signal['description'] = line
            
            if current_signal and len(current_signal['description']) > 20:
                signals.append(current_signal)
                current_signal = None
        
        if current_signal and current_signal['description']:
            signals.append(current_signal)
        
        return signals[:5]
    
    def research_with_reports(self, stock_code: str, trade_date: str,
                            market_report: str = '',
                            news_report: str = '',
                            fundamentals_report: str = '') -> Dict[str, Any]:
        """基于分析报告研究做空论点
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            market_report: 技术分析报告
            news_report: 新闻分析报告
            fundamentals_report: 基本面分析报告
            
        Returns:
            做空研究结果
        """
        result = self.run({
            'stock_code': stock_code,
            'trade_date': trade_date,
            'market_report': market_report,
            'news_report': news_report,
            'fundamentals_report': fundamentals_report,
            'task': 'bear_case'
        })
        
        if result['success']:
            parsed = self._parse_bear_result(result['output'])
            parsed['research_output'] = result['output']
            return parsed
        
        return {
            'bear_points': [],
            'risk_level': 'unknown',
            'downside_risk': 0.0,
            'confidence': 0.0,
            'error': result.get('error', 'Unknown error')
        }