"""
交易智能体图 - TradingAgentsGraph实现
"""
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from agent_integration.agents.base import AgentConfig
from agent_integration.agents.analysts.market_analyst import MarketAnalyst
from agent_integration.agents.analysts.news_analyst import NewsAnalyst
from agent_integration.agents.analysts.fundamentals_analyst import FundamentalsAnalyst
from agent_integration.agents.researchers.bull_researcher import BullResearcher
from agent_integration.agents.researchers.bear_researcher import BearResearcher
from agent_integration.agents.risk_mgmt.debate_aggregator import DebateAggregator
from agent_integration.graph.state import AgentState, create_initial_state

try:
    from agent_integration.memory.memory_manager import MemoryManager
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    MemoryManager = None

logger = logging.getLogger(__name__)


class TradingAgentsGraph:
    """交易智能体协作图
    
    编排和管理多智能体协作的工作流。
    支持顺序执行和并行执行模式。
    """
    
    def __init__(
        self,
        llm: Any = None,
        selected_analysts: List[str] = None,
        debug: bool = False,
        memory_manager: Any = None,
        include_memory_context: bool = True
    ):
        """初始化交易智能体图
        
        Args:
            llm: LLM适配器实例
            selected_analysts: 选择使用的分析师列表 ['market', 'news', 'fundamentals']
            debug: 是否开启调试模式
            memory_manager: 记忆管理器实例
            include_memory_context: 是否在分析时包含记忆上下文
        """
        self.debug = debug
        self.llm = llm
        self.selected_analysts = selected_analysts or ['market', 'news', 'fundamentals']
        self.memory_manager = memory_manager
        self.include_memory_context = include_memory_context
        
        self._analysts: Dict[str, Any] = {}
        self._bull_researcher: Optional[BullResearcher] = None
        self._bear_researcher: Optional[BearResearcher] = None
        self._debate_aggregator: Optional[DebateAggregator] = None
        
        self._initialize_agents()
    
    def _initialize_agents(self):
        """初始化所有智能体"""
        if self.llm is None:
            logger.warning("未配置LLM适配器，智能体将返回模拟结果")
            return
        
        try:
            if 'market' in self.selected_analysts:
                market_config = AgentConfig(
                    name='market_analyst',
                    role='market_analyst',
                    llm_adapter=self.llm
                )
                self._analysts['market'] = MarketAnalyst(market_config)
            
            if 'news' in self.selected_analysts:
                news_config = AgentConfig(
                    name='news_analyst',
                    role='news_analyst',
                    llm_adapter=self.llm
                )
                self._analysts['news'] = NewsAnalyst(news_config)
            
            if 'fundamentals' in self.selected_analysts:
                fund_config = AgentConfig(
                    name='fundamentals_analyst',
                    role='fundamentals_analyst',
                    llm_adapter=self.llm
                )
                self._analysts['fundamentals'] = FundamentalsAnalyst(fund_config)
            
            bull_config = AgentConfig(
                name='bull_researcher',
                role='bull_researcher',
                llm_adapter=self.llm
            )
            self._bull_researcher = BullResearcher(bull_config)
            
            bear_config = AgentConfig(
                name='bear_researcher',
                role='bear_researcher',
                llm_adapter=self.llm
            )
            self._bear_researcher = BearResearcher(bear_config)
            
            self._debate_aggregator = DebateAggregator(self.llm)
            
            if self.debug:
                logger.info(f"已初始化 {len(self._analysts)} 个分析师、2个研究员和辩论聚合器")
        
        except Exception as e:
            logger.error(f"初始化智能体失败: {e}")
    
    def _run_analysts_parallel(
        self,
        stock_code: str,
        trade_date: str,
        price_data: Any = None,
        news_list: List = None,
        fundamentals_data: Dict = None
    ) -> Dict[str, str]:
        """并行运行分析师
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            price_data: K线数据
            news_list: 新闻列表
            fundamentals_data: 基本面数据
            
        Returns:
            各分析师的报告字典
        """
        reports = {}
        
        if self.debug:
            logger.info(f"开始并行运行分析师: {self.selected_analysts}")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_key = {}
            
            if 'market' in self._analysts and price_data is not None:
                future = executor.submit(
                    self._analysts['market'].run,
                    {'stock_code': stock_code, 'price_data': price_data}
                )
                future_to_key[future] = 'market'
            
            if 'news' in self._analysts and news_list:
                future = executor.submit(
                    self._analysts['news'].run,
                    {'stock_code': stock_code, 'news_list': news_list}
                )
                future_to_key[future] = 'news'
            
            if 'fundamentals' in self._analysts and fundamentals_data:
                # 转换数据格式以匹配 FundamentalsAnalyst 期望的格式
                fundamentals_input = {
                    'stock_code': stock_code,
                    'financial_data': {'profitability': fundamentals_data.get('profitability', {})},
                    'valuation_data': fundamentals_data.get('valuation', {}),
                    'growth_data': fundamentals_data.get('growth', {}),
                }
                future = executor.submit(
                    self._analysts['fundamentals'].run,
                    fundamentals_input
                )
                future_to_key[future] = 'fundamentals'
            
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    result = future.result()
                    if result['success']:
                        reports[key] = result['output']
                    else:
                        reports[key] = f"分析失败: {result.get('error', 'Unknown error')}"
                    if self.debug:
                        logger.info(f"分析师 {key} 完成")
                except Exception as e:
                    reports[key] = f"执行异常: {str(e)}"
                    logger.error(f"分析师 {key} 执行异常: {e}")
        
        return reports
    
    def _run_researchers(
        self,
        stock_code: str,
        trade_date: str,
        reports: Dict[str, str]
    ) -> Dict[str, Any]:
        """运行牛市和熊市研究员
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            reports: 分析师报告
            
        Returns:
            研究结果字典
        """
        results = {
            'bull_research': '',
            'bear_research': '',
            'bull_confidence': 0.0,
            'bear_confidence': 0.0
        }
        
        if self.debug:
            logger.info("开始运行研究员")
        
        market_report = reports.get('market', '')
        news_report = reports.get('news', '')
        fundamentals_report = reports.get('fundamentals', '')
        
        if self._bull_researcher:
            try:
                bull_result = self._bull_researcher.research_with_reports(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    market_report=market_report,
                    news_report=news_report,
                    fundamentals_report=fundamentals_report
                )
                results['bull_research'] = bull_result.get('raw_output', bull_result.get('research_output', ''))
                results['bull_confidence'] = bull_result.get('confidence', 0.0)
            except Exception as e:
                results['bull_research'] = f"执行异常: {str(e)}"
                logger.error(f"BullResearcher执行异常: {e}")
        
        if self._bear_researcher:
            try:
                bear_result = self._bear_researcher.research_with_reports(
                    stock_code=stock_code,
                    trade_date=trade_date,
                    market_report=market_report,
                    news_report=news_report,
                    fundamentals_report=fundamentals_report
                )
                results['bear_research'] = bear_result.get('raw_output', bear_result.get('research_output', ''))
                results['bear_confidence'] = bear_result.get('confidence', 0.0)
            except Exception as e:
                results['bear_research'] = f"执行异常: {str(e)}"
                logger.error(f"BearResearcher执行异常: {e}")
        
        return results
    
    def _run_debate_phase(
        self,
        investment_decision: str,
        bull_research: str,
        bear_research: str
    ) -> Dict[str, Any]:
        """运行辩论阶段
        
        Args:
            investment_decision: 投资决策
            bull_research: 做多研究
            bear_research: 做空研究
            
        Returns:
            辩论结果字典
        """
        if self._debate_aggregator is None:
            return {
                'conservative_view': {'stance': '保守', 'arguments': [], 'risk_points': [], 'confidence': 0.5, 'recommended_position': 0.1},
                'neutral_view': {'stance': '中性', 'arguments': [], 'risk_points': [], 'confidence': 0.5, 'recommended_position': 0.2},
                'aggressive_view': {'stance': '激进', 'arguments': [], 'risk_points': [], 'confidence': 0.5, 'recommended_position': 0.3},
                'final_risk_level': 'MEDIUM',
                'recommended_position': 0.2,
                'consensus': '辩论器未初始化'
            }
        
        if self.debug:
            logger.info("开始运行辩论阶段")
        
        try:
            debate_result = self._debate_aggregator.run_debate(
                investment_decision=investment_decision,
                bull_research=bull_research,
                bear_research=bear_research
            )
            return debate_result
        except Exception as e:
            logger.error(f"辩论阶段执行异常: {e}")
            return {
                'conservative_view': {'stance': '保守', 'arguments': [], 'risk_points': [], 'confidence': 0.5, 'recommended_position': 0.1},
                'neutral_view': {'stance': '中性', 'arguments': [], 'risk_points': [], 'confidence': 0.5, 'recommended_position': 0.2},
                'aggressive_view': {'stance': '激进', 'arguments': [], 'risk_points': [], 'confidence': 0.5, 'recommended_position': 0.3},
                'final_risk_level': 'MEDIUM',
                'recommended_position': 0.2,
                'consensus': f'辩论失败: {str(e)}'
            }
    
    def _generate_final_decision(
        self,
        stock_code: str,
        reports: Dict[str, str],
        research: Dict[str, Any]
    ) -> Dict[str, Any]:
        """生成最终决策
        
        Args:
            stock_code: 股票代码
            reports: 分析师报告
            research: 研究结果
            
        Returns:
            最终决策字典
        """
        bull_conf = research.get('bull_confidence', 0.5)
        bear_conf = research.get('bear_confidence', 0.5)
        
        if bull_conf > bear_conf + 0.2:
            final_decision = '买入'
            confidence = bull_conf
        elif bear_conf > bull_conf + 0.2:
            final_decision = '卖出/观望'
            confidence = bear_conf
        else:
            final_decision = '观望'
            confidence = 0.5
        
        return {
            'final_decision': final_decision,
            'confidence': confidence,
            'bull_confidence': bull_conf,
            'bear_confidence': bear_conf,
            'reasoning': f"做多置信度={bull_conf:.2f}, 做空置信度={bear_conf:.2f}"
        }
    
    def propagate(
        self,
        company_of_interest: str,
        trade_date: str = '',
        price_data: Any = None,
        news_list: List = None,
        fundamentals_data: Dict = None
    ) -> Dict[str, Any]:
        """运行完整的智能体工作流
        
        Args:
            company_of_interest: 股票代码
            trade_date: 交易日期
            price_data: K线数据 (DataFrame)
            news_list: 新闻列表 (List[NewsItem])
            fundamentals_data: 基本面数据 (Dict)
            
        Returns:
            {
                'final_decision': str,  # 买入/卖出/持有/观望
                'confidence': float,     # 置信度 0.0-1.0
                'reports': {...},
                'bull_research': str,
                'bear_research': str,
                'debate_result': {...},
                'memory_context': list,  # 相关记忆上下文
                'state': AgentState
            }
        """
        state = create_initial_state(company_of_interest, trade_date)
        
        if self.debug:
            logger.info(f"开始传播工作流: company={company_of_interest}, date={trade_date}")
        
        # 获取记忆上下文
        memory_context = []
        if self.include_memory_context and self.memory_manager is not None:
            try:
                memory_context = self.memory_manager.search_related(
                    symbol=company_of_interest,
                    query=f"{company_of_interest} 分析",
                    limit=5
                )
            except Exception as e:
                logger.warning(f"获取记忆上下文失败: {e}")
        
        reports = self._run_analysts_parallel(
            stock_code=company_of_interest,
            trade_date=trade_date,
            price_data=price_data,
            news_list=news_list,
            fundamentals_data=fundamentals_data
        )
        
        state['market_report'] = reports.get('market', '')
        state['news_report'] = reports.get('news', '')
        state['fundamentals_report'] = reports.get('fundamentals', '')
        
        research = self._run_researchers(
            stock_code=company_of_interest,
            trade_date=trade_date,
            reports=reports
        )
        
        state['bull_research'] = research.get('bull_research', '')
        state['bear_research'] = research.get('bear_research', '')
        
        final = self._generate_final_decision(
            stock_code=company_of_interest,
            reports=reports,
            research=research
        )
        
        state['final_decision'] = final['final_decision']
        state['confidence'] = final['confidence']
        
        debate_result = self._run_debate_phase(
            investment_decision=final['final_decision'],
            bull_research=research.get('bull_research', ''),
            bear_research=research.get('bear_research', '')
        )
        
        state['investment_decision'] = final['final_decision']
        state['risk_assessment'] = debate_result.get('final_risk_level', 'MEDIUM')
        
        result = {
            'final_decision': final['final_decision'],
            'confidence': final['confidence'],
            'reasoning': final['reasoning'],
            'reports': reports,
            'bull_research': research.get('bull_research', ''),
            'bear_research': research.get('bear_research', ''),
            'bull_confidence': research.get('bull_confidence', 0.0),
            'bear_confidence': research.get('bear_confidence', 0.0),
            'debate_result': debate_result,
            'memory_context': memory_context,
            'state': state
        }
        
        # 保存结果到记忆
        if self.memory_manager is not None:
            try:
                self.memory_manager.save_analysis_result(
                    symbol=company_of_interest,
                    trade_date=trade_date,
                    result=result
                )
            except Exception as e:
                logger.warning(f"保存记忆失败: {e}")
        
        return result
    
    def add_agent(self, agent_id: str, agent: Any):
        """添加智能体
        
        Args:
            agent_id: 智能体ID
            agent: 智能体实例
        """
        self._analysts[agent_id] = agent
    
    def add_edge(self, from_id: str, to_id: str, edge_type: str = 'default'):
        """添加智能体连接边
        
        Args:
            from_id: 起始智能体ID
            to_id: 目标智能体ID
            edge_type: 边类型
        """
        pass
    
    def execute(self, start_id: str, input_data: Dict[str, Any]) -> Any:
        """执行工作流
        
        Args:
            start_id: 起始智能体ID
            input_data: 输入数据
            
        Returns:
            执行结果
        """
        return self.propagate(
            company_of_interest=input_data.get('company_of_interest', ''),
            trade_date=input_data.get('trade_date', ''),
            price_data=input_data.get('price_data'),
            news_list=input_data.get('news_list'),
            fundamentals_data=input_data.get('fundamentals_data')
        )
    
    def get_execution_order(self) -> List[str]:
        """获取执行顺序
        
        Returns:
            智能体执行顺序
        """
        order = list(self.selected_analysts)
        order.extend(['bull_researcher', 'bear_researcher'])
        return order