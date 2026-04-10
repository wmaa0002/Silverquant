"""
辩论聚合器 - DebateAggregator
"""
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent_integration.agents.base import AgentConfig
from agent_integration.agents.risk_mgmt.conservative_debator import ConservativeDebater
from agent_integration.agents.risk_mgmt.neutral_debator import NeutralDebater
from agent_integration.agents.risk_mgmt.aggressive_debator import AggressiveDebater


class DebateAggregator:
    """辩论聚合器
    
    协调三种不同风险偏好的辩论者进行辩论，
    并综合他们的观点得出最终风险等级。
    """
    
    def __init__(self, llm=None):
        """初始化辩论聚合器
        
        Args:
            llm: LLM适配器实例
        """
        self.llm = llm
        
        self._conservative = None
        self._neutral = None
        self._aggressive = None
        
        self._initialize_debaters()
    
    def _initialize_debaters(self):
        """初始化辩论者"""
        if self.llm is None:
            return
        
        conservative_config = AgentConfig(
            name='conservative_debater',
            role='risk_debater',
            llm_adapter=self.llm
        )
        self._conservative = ConservativeDebater(conservative_config)
        
        neutral_config = AgentConfig(
            name='neutral_debater',
            role='risk_debater',
            llm_adapter=self.llm
        )
        self._neutral = NeutralDebater(neutral_config)
        
        aggressive_config = AgentConfig(
            name='aggressive_debater',
            role='risk_debater',
            llm_adapter=self.llm
        )
        self._aggressive = AggressiveDebater(aggressive_config)
    
    def run_debate(self, investment_decision: str, bull_research: str = '',
                  bear_research: str = '') -> Dict[str, Any]:
        """运行三方辩论
        
        Args:
            investment_decision: 投资决策
            bull_research: 做多研究
            bear_research: 做空研究
            
        Returns:
            {
                'conservative_view': {...},
                'neutral_view': {...},
                'aggressive_view': {...},
                'final_risk_level': str,  # LOW/MEDIUM/HIGH
                'recommended_position': float,
                'consensus': str
            }
        """
        conservative_view = {
            'stance': '保守',
            'arguments': [],
            'risk_points': [],
            'confidence': 0.5,
            'recommended_position': 0.1
        }
        neutral_view = {
            'stance': '中性',
            'arguments': [],
            'risk_points': [],
            'confidence': 0.5,
            'recommended_position': 0.2
        }
        aggressive_view = {
            'stance': '激进',
            'arguments': [],
            'risk_points': [],
            'confidence': 0.5,
            'recommended_position': 0.3
        }
        
        if self.llm is None:
            return {
                'conservative_view': conservative_view,
                'neutral_view': neutral_view,
                'aggressive_view': aggressive_view,
                'final_risk_level': 'MEDIUM',
                'recommended_position': 0.2,
                'consensus': '无LLM，使用默认保守估计'
            }
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_debater = {
                executor.submit(
                    self._conservative.debate,
                    investment_decision, bull_research, bear_research
                ): 'conservative',
                executor.submit(
                    self._neutral.debate,
                    investment_decision, bull_research, bear_research
                ): 'neutral',
                executor.submit(
                    self._aggressive.debate,
                    investment_decision, bull_research, bear_research
                ): 'aggressive'
            }
            
            for future in as_completed(future_to_debater):
                debater_type = future_to_debater[future]
                try:
                    result = future.result()
                    if debater_type == 'conservative':
                        conservative_view = result
                    elif debater_type == 'neutral':
                        neutral_view = result
                    elif debater_type == 'aggressive':
                        aggressive_view = result
                except Exception as e:
                    print(f"Debater {debater_type} failed: {e}")
        
        final_risk_level, recommended_position, consensus = self._aggregate_views(
            conservative_view, neutral_view, aggressive_view
        )
        
        return {
            'conservative_view': conservative_view,
            'neutral_view': neutral_view,
            'aggressive_view': aggressive_view,
            'final_risk_level': final_risk_level,
            'recommended_position': recommended_position,
            'consensus': consensus
        }
    
    def _aggregate_views(self, conservative: Dict, neutral: Dict,
                       aggressive: Dict) -> tuple:
        """聚合三方观点
        
        Args:
            conservative: 保守观点
            neutral: 中性观点
            aggressive: 激进观点
            
        Returns:
            (final_risk_level, recommended_position, consensus)
        """
        risk_counts = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0}
        
        conservative_risk = self._assess_risk_level(conservative)
        neutral_risk = self._assess_risk_level(neutral)
        aggressive_risk = self._assess_risk_level(aggressive)
        
        risk_counts[conservative_risk] += 1
        risk_counts[neutral_risk] += 1
        risk_counts[aggressive_risk] += 1
        
        if risk_counts['HIGH'] >= 2:
            final_risk = 'HIGH'
            recommended_position = 0.0
        elif risk_counts['LOW'] >= 2:
            final_risk = 'LOW'
            recommended_position = 0.3
        else:
            final_risk = 'MEDIUM'
            recommended_position = 0.15
        
        avg_confidence = (
            conservative.get('confidence', 0.5) +
            neutral.get('confidence', 0.5) +
            aggressive.get('confidence', 0.5)
        ) / 3
        
        consensus = f"3方辩论完成，置信度{avg_confidence:.2f}"
        
        return final_risk, recommended_position, consensus
    
    def _assess_risk_level(self, view: Dict) -> str:
        """根据观点评估风险等级
        
        Args:
            view: 辩论观点
            
        Returns:
            LOW/MEDIUM/HIGH
        """
        recommended_position = view.get('recommended_position', 0.2)
        
        if recommended_position >= 0.25:
            return 'LOW'
        elif recommended_position >= 0.15:
            return 'MEDIUM'
        else:
            return 'HIGH'