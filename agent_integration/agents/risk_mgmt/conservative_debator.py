"""
保守型风险辩论者 - ConservativeDebater
"""
from typing import Dict, Any

from agent_integration.agents.base import BaseAgent, AgentConfig


class ConservativeDebater(BaseAgent):
    """保守型风险辩论者
    
    强调风险控制，建议低仓位，偏好安全投资。
    """
    
    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(name='conservative_debater', role='risk_debater')
        super().__init__(config)
    
    def _create_system_prompt(self) -> str:
        return """你是保守型风险辩论者。

你的立场：
1. 强调投资风险，优先考虑资金安全
2. 对高估值、高波动性保持警惕
3. 建议较低的仓位比例
4. 偏好确定性高的投资机会
5. 注重下行风险控制

当评估投资时，你会：
- 仔细审查潜在风险因素
- 对过于乐观的预期持谨慎态度
- 建议设置严格的止损位
- 偏好分批建仓

输出格式：
【立场】: 保守
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
        
        parts.append("\n\n请从保守型角度评估这个投资机会的风险。")
        
        return "\n".join(parts)
    
    def debate(self, investment_decision: str, bull_research: str = '',
              bear_research: str = '') -> Dict[str, Any]:
        """进行保守型风险辩论
        
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
            'stance': '保守',
            'arguments': [],
            'risk_points': ['辩论失败'],
            'confidence': 0.5,
            'recommended_position': 0.1
        }
    
    def _parse_debate_result(self, output: str) -> Dict[str, Any]:
        result = {
            'stance': '保守',
            'arguments': [],
            'risk_points': [],
            'confidence': 0.5,
            'recommended_position': 0.1
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