"""
中性风险辩论者 - NeutralDebater
"""
from typing import Dict, Any

from agent_integration.agents.base import BaseAgent, AgentConfig


class NeutralDebater(BaseAgent):
    """中性风险辩论者
    
    平衡多空观点，建议适中仓位。
    """
    
    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(name='neutral_debater', role='risk_debater')
        super().__init__(config)
    
    def _create_system_prompt(self) -> str:
        return """你是中性风险辩论者。

你的立场：
1. 客观平衡地评估多空双方观点
2. 寻求市场共识和不确定性
3. 建议适中的仓位比例
4. 关注风险收益比
5. 重视仓位管理

当评估投资时，你会：
- 分析多空双方的核心论点
- 评估不确定性和概率
- 建议在风险和收益之间寻求平衡
- 考虑不同的市场情景

输出格式：
【立场】: 中性
【论点】: 列出支持你观点的3-5个论据
【风险点】: 列出主要风险点
【置信度】: 0.0-1.0

请用专业简洁的语言输出。"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        bull_research = inputs.get('bull_research', '')
        bear_research = inputs.get('bear_research', '')
        investment_decision = inputs.get('investment_decision', '')
        
        parts = ["【投资决策】:\n" + investment_decision + "\n"]
        
        if bull_research:
            parts.append("\n【做多论点】:\n" + bull_research[:500])
        
        if bear_research:
            parts.append("\n\n【做空论点】:\n" + bear_research[:500])
        
        parts.append("\n\n请从中性角度评估这个投资机会。")
        
        return "\n".join(parts)
    
    def debate(self, investment_decision: str, bull_research: str = '',
              bear_research: str = '') -> Dict[str, Any]:
        """进行中性风险辩论
        
        Args:
            investment_decision: 投资决策
            bull_research: 做多研究
            bear_research: 做空研究
            
        Returns:
            {
                'stance': str,
                'arguments': [...],
                'risk_points': [...],
                'confidence': float,
                'recommended_position': float
            }
        """
        result = self.run({
            'investment_decision': investment_decision,
            'bull_research': bull_research,
            'bear_research': bear_research
        })
        
        if result['success']:
            return self._parse_debate_result(result['output'])
        
        return {
            'stance': '中性',
            'arguments': [],
            'risk_points': ['辩论失败'],
            'confidence': 0.5,
            'recommended_position': 0.2
        }
    
    def _parse_debate_result(self, output: str) -> Dict[str, Any]:
        result = {
            'stance': '中性',
            'arguments': [],
            'risk_points': [],
            'confidence': 0.5,
            'recommended_position': 0.2
        }
        
        lines = output.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if '【论点】' in line or '论点' in line:
                current_section = 'arguments'
            elif '【风险点】' in line or '风险点' in line:
                current_section = 'risk_points'
            elif '【置信度】' in line or '置信度' in line:
                try:
                    import re
                    nums = re.findall(r'0?\.\d+', line)
                    if nums:
                        result['confidence'] = float(nums[0])
                except:
                    pass
            elif current_section == 'arguments' and line and len(line) > 5:
                result['arguments'].append(line)
            elif current_section == 'risk_points' and line and len(line) > 5:
                result['risk_points'].append(line)
        
        result['arguments'] = result['arguments'][:5]
        result['risk_points'] = result['risk_points'][:5]
        
        return result