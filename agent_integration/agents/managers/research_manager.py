"""
研究经理 - ResearchManager实现
"""
from typing import Dict, Any, List, Optional

from agent_integration.agents.base import BaseAgent, AgentConfig


class ResearchManager(BaseAgent):
    """研究经理智能体
    
    负责协调研究员和分析师的工作，整合研究结果。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化研究经理"""
        super().__init__(config)
        self.analysts: List[BaseAgent] = []
        self.researchers: List[BaseAgent] = []
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是A股市场研究经理，专注于综合多方面的研究结果，形成投资建议。

你的职责：
1. 综合牛市研究员和熊市研究员的研究成果
2. 分析技术面、基本面、消息面的整体一致性
3. 识别主要矛盾和关键驱动因素
4. 形成明确的投资建议（强烈买入/买入/观望/卖出/强烈卖出）
5. 评估置信度

输出要求：
1. 给出明确的投资建议
2. 列出3-5个核心投资要点
3. 说明投资逻辑和风险
4. 标注置信度（0.0-1.0）

请用专业简洁的语言输出。"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """处理输入数据"""
        stock_code = inputs.get('stock_code', '')
        market_report = inputs.get('market_report', '')
        news_report = inputs.get('news_report', '')
        fundamentals_report = inputs.get('fundamentals_report', '')
        bull_research = inputs.get('bull_research', '')
        bear_research = inputs.get('bear_research', '')
        
        parts = [f"股票代码: {stock_code}\n"]
        
        if inputs.get('trade_date'):
            parts.append(f"交易日期: {inputs.get('trade_date')}\n")
        
        if market_report:
            parts.append("【技术分析报告】\n")
            parts.append(market_report[:500] if len(market_report) > 500 else market_report)
            parts.append("\n\n")
        
        if news_report:
            parts.append("【新闻分析报告】\n")
            parts.append(news_report[:500] if len(news_report) > 500 else news_report)
            parts.append("\n\n")
        
        if fundamentals_report:
            parts.append("【基本面分析报告】\n")
            parts.append(fundamentals_report[:500] if len(fundamentals_report) > 500 else fundamentals_report)
            parts.append("\n\n")
        
        if bull_research:
            parts.append("【牛市研究员观点】\n")
            parts.append(bull_research[:800] if len(bull_research) > 800 else bull_research)
            parts.append("\n\n")
        
        if bear_research:
            parts.append("【熊市研究员观点】\n")
            parts.append(bear_research[:800] if len(bear_research) > 800 else bear_research)
            parts.append("\n\n")
        
        parts.append("请综合以上研究结果，形成投资建议。")
        
        return "\n".join(parts)
    
    def add_analyst(self, analyst: BaseAgent):
        """添加分析师
        
        Args:
            analyst: 分析师实例
        """
        self.analysts.append(analyst)
    
    def add_researcher(self, researcher: BaseAgent):
        """添加研究员
        
        Args:
            researcher: 研究员实例
        """
        self.researchers.append(researcher)
    
    def conduct_research(
        self,
        stock_code: str,
        reports: Dict[str, str] = None,
        research: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """执行全面研究
        
        Args:
            stock_code: 股票代码
            reports: 分析师报告字典 {'market': '', 'news': '', 'fundamentals': ''}
            research: 研究结果字典
            
        Returns:
            综合研究报告 {
                'recommendation': str,
                'reasoning': str,
                'key_points': [...],
                'confidence': float
            }
        """
        inputs = {'stock_code': stock_code}
        
        if reports:
            inputs['market_report'] = reports.get('market', '')
            inputs['news_report'] = reports.get('news', '')
            inputs['fundamentals_report'] = reports.get('fundamentals', '')
        
        if research:
            inputs['bull_research'] = research.get('bull_research', '')
            inputs['bear_research'] = research.get('bear_research', '')
        
        result = self.run(inputs)
        
        if result['success']:
            return self._parse_research_result(result['output'])
        
        return {
            'recommendation': '观望',
            'reasoning': f"研究失败: {result.get('error', 'Unknown error')}",
            'key_points': [],
            'confidence': 0.0
        }
    
    def _parse_research_result(self, output: str) -> Dict[str, Any]:
        """解析研究结果"""
        result = {
            'recommendation': '观望',
            'reasoning': output,
            'key_points': [],
            'confidence': 0.5
        }
        
        recommendation_keywords = {
            '强烈买入': 0.9,
            '买入': 0.7,
            '观望': 0.5,
            '卖出': 0.3,
            '强烈卖出': 0.1
        }
        
        lines = output.split('\n')
        for line in lines:
            line_stripped = line.strip()
            for keyword, conf in recommendation_keywords.items():
                if keyword in line_stripped:
                    result['recommendation'] = keyword
                    result['confidence'] = conf
                    break
            
            if '置信度' in line_stripped or 'confidence' in line_stripped.lower():
                try:
                    import re
                    nums = re.findall(r'0?\.\d+', line_stripped)
                    if nums:
                        result['confidence'] = float(nums[0])
                except:
                    pass
            
            if line_stripped and len(line_stripped) > 10:
                result['key_points'].append(line_stripped)
        
        result['key_points'] = result['key_points'][:5]
        
        return result
    
    def synthesize_findings(self, findings: List[Dict[str, Any]]) -> str:
        """综合研究发现
        
        Args:
            findings: 发现列表
            
        Returns:
            综合结论
        """
        if not findings:
            return "无研究发现"
        
        synthesis = "【研究发现综合】\n\n"
        
        for i, finding in enumerate(findings[:5], 1):
            source = finding.get('source', 'Unknown')
            content = finding.get('content', str(finding))
            synthesis += f"{i}. [{source}]\n{content[:200]}...\n\n"
        
        if self._llm:
            inputs = {'synthesis_content': synthesis}
            result = self.run(inputs)
            if result['success']:
                return result['output']
        
        return synthesis