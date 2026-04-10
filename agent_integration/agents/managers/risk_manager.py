"""
风控经理 - RiskManager实现
"""
from typing import Dict, Any, List, Optional

from agent_integration.agents.base import BaseAgent, AgentConfig


class RiskManager(BaseAgent):
    """风控经理智能体
    
    负责评估交易风险，提供风险控制建议。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化风控经理"""
        super().__init__(config)
        self.max_position_size = 0.3
        self.max_portfolio_risk = 0.15
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是A股市场风控经理，专注于评估交易风险和提供仓位建议。

你的职责：
1. 评估投资决策的风险等级（LOW/MEDIUM/HIGH）
2. 根据风险等级建议仓位大小
3. 设置止损位和风险限额
4. 检查交易合规性

风险等级定义：
- LOW（低风险）：估值合理、趋势向上、基本面稳健
- MEDIUM（中风险）：估值适中、多空交织、需要观望
- HIGH（高风险）：估值过高、趋势向下、基本面恶化

仓位建议规则：
- LOW: 30%仓位（积极操作）
- MEDIUM: 15%仓位（谨慎操作）
- HIGH: 0%仓位（不建议操作）

输出要求：
1. 明确风险等级
2. 建议仓位比例
3. 设置止损位
4. 列出风险因素

请用专业简洁的语言输出。"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """处理输入数据"""
        stock_code = inputs.get('stock_code', '')
        investment_decision = inputs.get('investment_decision', '')
        confidence = inputs.get('confidence', 0.0)
        bull_research = inputs.get('bull_research', '')
        bear_research = inputs.get('bear_research', '')
        current_price = inputs.get('current_price', 0.0)
        
        parts = [f"股票代码: {stock_code}\n"]
        
        if investment_decision:
            parts.append(f"投资决策: {investment_decision}\n")
        
        parts.append(f"置信度: {confidence:.2f}\n")
        
        if current_price > 0:
            parts.append(f"当前价格: {current_price:.2f}\n")
        
        if bull_research:
            parts.append("\n【做多论点摘要】\n")
            parts.append(bull_research[:300] if len(bull_research) > 300 else bull_research)
        
        if bear_research:
            parts.append("\n【做空论点摘要】\n")
            parts.append(bear_research[:300] if len(bear_research) > 300 else bear_research)
        
        parts.append("\n\n请评估风险等级并给出仓位建议。")
        
        return "\n".join(parts)
    
    def assess_risk(self, investment_decision: str, confidence: float = 0.5,
                   bull_research: str = '', bear_research: str = '',
                   stock_code: str = '', current_price: float = 0.0) -> Dict[str, Any]:
        """评估交易风险
        
        Args:
            investment_decision: 投资决策
            confidence: 置信度
            bull_research: 做多研究
            bear_research: 做空研究
            stock_code: 股票代码
            current_price: 当前价格
            
        Returns:
            风险评估结果 {
                'risk_level': str,  # LOW/MEDIUM/HIGH
                'risk_score': float,  # 0.0-1.0
                'risk_factors': [...],
                'stop_loss': float
            }
        """
        result = self.run({
            'stock_code': stock_code,
            'investment_decision': investment_decision,
            'confidence': confidence,
            'bull_research': bull_research,
            'bear_research': bear_research,
            'current_price': current_price
        })
        
        if result['success']:
            return self._parse_risk_result(result['output'], current_price)
        
        return {
            'risk_level': 'MEDIUM',
            'risk_score': 0.5,
            'risk_factors': ['Risk assessment failed'],
            'stop_loss': current_price * 0.95 if current_price > 0 else 0.0
        }
    
    def _parse_risk_result(self, output: str, current_price: float = 0.0) -> Dict[str, Any]:
        """解析风险评估结果"""
        result = {
            'risk_level': 'MEDIUM',
            'risk_score': 0.5,
            'risk_factors': [],
            'stop_loss': current_price * 0.95 if current_price > 0 else 0.0
        }
        
        risk_keywords = {
            'HIGH': ('HIGH', 0.8),
            'MEDIUM': ('MEDIUM', 0.5),
            'LOW': ('LOW', 0.2)
        }
        
        lines = output.split('\n')
        for line in lines:
            line_stripped = line.strip()
            for keyword, (level, score) in risk_keywords.items():
                if keyword in line_stripped.upper():
                    result['risk_level'] = level
                    result['risk_score'] = score
            
            if '止损' in line_stripped or 'stop loss' in line_stripped.lower():
                try:
                    import re
                    nums = re.findall(r'\d+\.?\d*', line_stripped)
                    if nums:
                        result['stop_loss'] = float(nums[0])
                except:
                    pass
            
            if line_stripped and len(line_stripped) > 5:
                result['risk_factors'].append(line_stripped)
        
        result['risk_factors'] = result['risk_factors'][:5]
        
        return result
    
    def suggest_position_size(self, stock_code: str, risk_level: str = 'MEDIUM') -> float:
        """建议仓位大小
        
        Args:
            stock_code: 股票代码
            risk_level: 风险等级 LOW/MEDIUM/HIGH
            
        Returns:
            建议仓位比例 (0.0-1.0)
        """
        position_map = {
            'LOW': 0.30,
            'MEDIUM': 0.15,
            'HIGH': 0.0
        }
        
        return position_map.get(risk_level.upper(), 0.15)
    
    def check_limits(self, position: Dict[str, Any]) -> bool:
        """检查仓位限制
        
        Args:
            position: 持仓信息 {
                'stock_code': str,
                'quantity': int,
                'avg_price': float,
                'current_value': float
            }
            
        Returns:
            是否超过限制
        """
        current_value = position.get('current_value', 0.0)
        
        if current_value > self.max_position_size * 1000000:
            return False
        
        return True
    
    def validate_trade(self, trade: Dict[str, Any]) -> tuple:
        """验证交易合规性
        
        Args:
            trade: 交易信息 {
                'action': str,  # BUY/SELL
                'stock_code': str,
                'quantity': int,
                'price': float
            }
            
        Returns:
            (是否合规, 原因列表)
        """
        reasons = []
        is_valid = True
        
        action = trade.get('action', '')
        stock_code = trade.get('stock_code', '')
        quantity = trade.get('quantity', 0)
        price = trade.get('price', 0.0)
        
        if not action or action not in ['BUY', 'SELL']:
            is_valid = False
            reasons.append("无效的交易动作")
        
        if not stock_code or len(stock_code) != 6:
            is_valid = False
            reasons.append("无效的股票代码")
        
        if quantity <= 0:
            is_valid = False
            reasons.append("数量必须大于0")
        
        if price <= 0:
            is_valid = False
            reasons.append("价格必须大于0")
        
        if stock_code.startswith('688') and quantity < 100:
            is_valid = False
            reasons.append("科创板股票最少买入100股")
        
        return is_valid, reasons