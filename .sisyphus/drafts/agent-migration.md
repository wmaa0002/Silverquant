# 智能体迁移详细实现方案

> **生成时间**: 2026-03-29
> **模块**: agent_integration/agents/

---

## 1. 智能体系统概览

### 1.1 TradingAgents-CN智能体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Multi-Agent System Architecture                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐                                                       │
│  │  Analysts   │ ← 5个分析师 (情报收集)                              │
│  │             │   • market_analyst      (技术分析)                   │
│  │             │   • fundamentals_analyst (基本面)                    │
│  └──────┬──────┘   • news_analyst        (新闻)                      │
│         │         • social_media_analyst (社交)                       │
│         │         • china_market_analyst (A股专用)                    │
│         ▼                                                               │
│  ┌─────────────┐                                                       │
│  │ Researchers │ ← 2个研究员 (论点构建)                              │
│  │             │   • bull_researcher   (看涨论点)                   │
│  └──────┬──────┘   • bear_researcher   (看跌论点)                   │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────┐                                                   │
│  │ ResearchManager │ ← 决策协调                                       │
│  └──────┬──────────┘                                                   │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────┐                                                   │
│  │ Risk Debaters  │ ← 3个风险辩论                                    │
│  │                 │   • conservative_debator (保守)                  │
│  └──────┬──────────┘   • neutral_debator    (中性)                  │
│         │             • aggressive_debator (激进)                    │
│         ▼                                                               │
│  ┌─────────────────┐                                                   │
│  │  RiskManager    │ ← 风险决策                                       │
│  └──────┬──────────┘                                                   │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────┐                                                   │
│  │     Trader      │ ← 最终交易执行                                   │
│  └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 智能体文件映射

| 智能体 | 源文件 | 目标文件 | 职责 |
|--------|--------|----------|------|
| Market Analyst | `analysts/market_analyst.py` | `analysts/market_analyst.py` | 技术分析,价格趋势 |
| Fundamentals Analyst | `analysts/fundamentals_analyst.py` | `analysts/fundamentals_analyst.py` | 财务报表,估值 |
| News Analyst | `analysts/news_analyst.py` | `analysts/news_analyst.py` | 新闻情绪分析 |
| Social Media Analyst | `analysts/social_media_analyst.py` | `analysts/social_media_analyst.py` | 社交媒体情绪 |
| China Market Analyst | `analysts/china_market_analyst.py` | `analysts/china_market_analyst.py` | A股特定分析 |
| Bull Researcher | `researchers/bull_researcher.py` | `researchers/bull_researcher.py` | 看涨论点 |
| Bear Researcher | `researchers/bear_researcher.py` | `researchers/bear_researcher.py` | 看跌论点 |
| Research Manager | `managers/research_manager.py` | `managers/research_manager.py` | 协调研究流程 |
| Conservative Debator | `risk_mgmt/conservative_debator.py` | `risk_mgmt/conservative_debator.py` | 保守风险 |
| Neutral Debator | `risk_mgmt/neutral_debator.py` | `risk_mgmt/neutral_debator.py` | 中性风险 |
| Aggressive Debator | `risk_mgmt/aggressive_debator.py` | `risk_mgmt/aggressive_debator.py` | 激进风险 |
| Risk Manager | `managers/risk_manager.py` | `managers/risk_manager.py` | 风险决策 |
| Trader | `trader/trader.py` | `trader/trader.py` | 交易执行 |

---

## 2. 智能体基类设计

### 2.1 BaseAgent抽象基类

```python
# agent_integration/agents/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import logging

from langchain.chat_models.base import BaseChatModel
from langchain.schema import HumanMessage, SystemMessage, AIMessage

logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """智能体配置"""
    name: str                           # 智能体名称
    role: str                          # 角色描述
    goal: str                          # 目标
    backstory: str                     # 背景故事
    llm: Optional[BaseChatModel] = None  # LLM实例
    verbose: bool = False             # 是否输出详细信息
    
    # 工具函数
    tools: List[Callable] = field(default_factory=list)
    
    # 记忆
    memory_enabled: bool = True
    memory_path: Optional[str] = None

class BaseAgent(ABC):
    """
    智能体基类
    
    所有Agent都继承此类，实现:
    - _create_system_prompt(): 创建系统提示
    - _process_input(): 处理输入
    - _validate_output(): 验证输出
    """
    
    def __init__(self, config: AgentConfig):
        """
        初始化智能体
        
        Args:
            config: 智能体配置
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.name}")
        self._history: List[Dict] = []
        
        # 验证配置
        if not config.name or not config.role:
            raise ValueError("name和role是必需配置")
    
    @property
    def name(self) -> str:
        """智能体名称"""
        return self.config.name
    
    @property
    def llm(self) -> BaseChatModel:
        """获取LLM"""
        if self.config.llm is None:
            raise ValueError(f"{self.name} 未配置LLM")
        return self.config.llm
    
    @abstractmethod
    def _create_system_prompt(self) -> str:
        """
        创建系统提示词
        
        Returns:
            str: 系统提示词
        """
        pass
    
    @abstractmethod
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入，生成用户提示
        
        Args:
            inputs: 输入数据
            
        Returns:
            str: 用户提示词
        """
        pass
    
    def _validate_output(self, output: str) -> bool:
        """
        验证输出
        
        Args:
            output: LLM输出
            
        Returns:
            bool: 是否有效
        """
        return True  # 默认不做验证
    
    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行智能体
        
        Args:
            inputs: 输入数据
            
        Returns:
            Dict: 输出结果
        """
        # 1. 创建系统提示
        system_prompt = self._create_system_prompt()
        
        # 2. 处理输入
        user_prompt = self._process_input(inputs)
        
        # 3. 构建消息
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        
        # 4. 调用LLM
        try:
            if self.config.verbose:
                self.logger.info(f"[{self.name}] 输入: {user_prompt[:100]}...")
            
            response = self.llm(messages)
            output = response.content
            
            # 5. 验证输出
            if not self._validate_output(output):
                self.logger.warning(f"[{self.name}] 输出验证失败")
            
            # 6. 记录历史
            self._history.append({
                'timestamp': datetime.now(),
                'inputs': inputs,
                'output': output,
            })
            
            if self.config.verbose:
                self.logger.info(f"[{self.name}] 输出: {output[:100]}...")
            
            return {
                'success': True,
                'output': output,
                'agent': self.name,
            }
            
        except Exception as e:
            self.logger.error(f"[{self.name}] 执行失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'agent': self.name,
            }
    
    def get_history(self) -> List[Dict]:
        """获取历史记录"""
        return self._history
```

---

## 3. 分析师 (Analysts)

### 3.1 Market Analyst (市场分析师)

```python
# agent_integration/agents/analysts/market_analyst.py

from typing import Dict, Any, List
from .base import BaseAgent, AgentConfig

class MarketAnalyst(BaseAgent):
    """
    市场分析师
    
    职责:
    - 技术分析 (K线, 均线, MACD, KDJ, RSI等)
    - 价格趋势判断
    - 成交量分析
    - 支撑位/压力位识别
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        # 默认配置
        if not config.goal:
            self.config.goal = "提供准确的技术分析报告"
        if not config.backstory:
            self.config.backstory = """你是一位资深的市场技术分析师，拥有10年以上的股票技术分析经验。
            擅长使用K线形态、均线系统、MACD、KDJ、RSI等技术指标进行分析。
            你的分析客观、准确，注重风险提示。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位专业的股票市场技术分析师。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

分析要求:
1. 结合K线形态、均线系统、技术指标进行综合分析
2. 识别关键的支撑位和压力位
3. 分析成交量变化趋势
4. 给出明确的技术面观点

输出格式:
请以结构化格式输出分析报告:
- 趋势判断: [上涨/下跌/震荡]
- 关键支撑位: XXX元
- 关键压力位: XXX元
- 技术指标信号: [买入/卖出/中性]
- 综合评分: X/10
- 风险提示: [如有]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入数据
        
        Args:
            inputs: {
                'symbol': '600519',
                'stock_name': '贵州茅台',
                'price_data': [...],  # K线数据
                'indicators': {...},  # 技术指标
                'trade_date': '2024-05-10',
            }
        """
        symbol = inputs.get('symbol', '')
        stock_name = inputs.get('stock_name', '')
        trade_date = inputs.get('trade_date', '')
        price_data = inputs.get('price_data', [])
        indicators = inputs.get('indicators', {})
        
        prompt = f"""请分析以下股票的技术面:

股票代码: {symbol}
股票名称: {stock_name}
分析日期: {trade_date}

K线数据 (最近10天):
{self._format_price_data(price_data)}

技术指标:
{self._format_indicators(indicators)}

请进行技术分析并给出投资建议。"""
        
        return prompt
    
    def _format_price_data(self, data: List[Dict]) -> str:
        """格式化K线数据"""
        if not data:
            return "无数据"
        
        lines = []
        for item in data[-10:]:  # 最近10天
            line = f"日期: {item.get('date', '')}, "
            line += f"开盘: {item.get('open', 0)}, "
            line += f"最高: {item.get('high', 0)}, "
            line += f"最低: {item.get('low', 0)}, "
            line += f"收盘: {item.get('close', 0)}, "
            line += f"成交量: {item.get('volume', 0)}"
            lines.append(line)
        
        return '\n'.join(lines)
    
    def _format_indicators(self, indicators: Dict) -> str:
        """格式化技术指标"""
        if not indicators:
            return "无数据"
        
        lines = []
        for name, value in indicators.items():
            if isinstance(value, dict):
                line = f"{name}: "
                line += ", ".join([f"{k}={v}" for k, v in value.items()])
                lines.append(line)
            else:
                lines.append(f"{name}: {value}")
        
        return '\n'.join(lines)
```

### 3.2 News Analyst (新闻分析师)

```python
# agent_integration/agents/analysts/news_analyst.py

from typing import Dict, Any, List
from .base import BaseAgent, AgentConfig

class NewsAnalyst(BaseAgent):
    """
    新闻分析师
    
    职责:
    - 新闻情绪分析
    - 突发事件识别
    - 政策影响评估
    - 舆论导向判断
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "分析新闻对股价的影响"
        if not config.backstory:
            self.config.backstory = """你是一位专业的财经新闻分析师，专注于分析新闻事件对股市的影响。
            你对政策动向、宏观经济、行业动态有敏锐的洞察力。
            能够从海量新闻中提取关键信息，判断其对股价的影响方向和程度。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位专业的财经新闻分析师。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

分析要求:
1. 分析新闻的整体情绪 (正面/负面/中性)
2. 评估新闻对股价的潜在影响
3. 识别关键的突发事件或政策变化
4. 判断舆论导向

输出格式:
请以结构化格式输出分析报告:
- 新闻情绪: [正面/负面/中性]
- 情绪强度: X/10
- 关键要点: [列出3-5个要点]
- 影响评估: [短期/中长期]
- 风险提示: [如有]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入数据
        
        Args:
            inputs: {
                'symbol': '600519',
                'stock_name': '贵州茅台',
                'news': [
                    {'title': '...', 'content': '...', 'source': '...', 'sentiment': '...'},
                    ...
                ],
                'trade_date': '2024-05-10',
            }
        """
        symbol = inputs.get('symbol', '')
        stock_name = inputs.get('stock_name', '')
        trade_date = inputs.get('trade_date', '')
        news_list = inputs.get('news', [])
        
        news_text = self._format_news(news_list)
        
        prompt = f"""请分析以下股票的新闻:

股票代码: {symbol}
股票名称: {stock_name}
分析日期: {trade_date}

新闻列表:
{news_text}

请进行新闻情绪分析并给出评估。"""
        
        return prompt
    
    def _format_news(self, news_list: List[Dict]) -> str:
        """格式化新闻列表"""
        if not news_list:
            return "无相关新闻"
        
        lines = []
        for i, news in enumerate(news_list[:10], 1):  # 最多10条
            line = f"[{i}] 来源: {news.get('source', '未知')}\n"
            line += f"    标题: {news.get('title', '')}\n"
            line += f"    摘要: {news.get('content', '')[:100]}..."
            lines.append(line)
        
        return '\n'.join(lines)
```

### 3.3 Fundamentals Analyst (基本面分析师)

```python
# agent_integration/agents/analysts/fundamentals_analyst.py

from typing import Dict, Any
from .base import BaseAgent, AgentConfig

class FundamentalsAnalyst(BaseAgent):
    """
    基本面分析师
    
    职责:
    - 财务报表分析 (营收、利润、现金流)
    - 估值分析 (PE、PB、PS)
    - 行业对比
    - 投资价值评估
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "评估股票的投资价值"
        if not config.backstory:
            self.config.backstory = """你是一位资深的基本面分析师，拥有CFA认证和10年以上的行业研究经验。
            精通财务分析、估值建模、行业比较。
            你的分析注重数据支撑，观点客观理性。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位专业的基本面分析师。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

分析要求:
1. 分析财务数据的质量和趋势
2. 评估估值水平的合理性
3. 与行业平均水平进行对比
4. 给出投资价值判断

输出格式:
请以结构化格式输出分析报告:
- 盈利能力: [强/中/弱]
- 成长性: [高/中/低]
- 估值水平: [高估/合理/低估]
- 财务风险: [低/中/高]
- 综合评分: X/10
- 投资建议: [买入/持有/卖出]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入数据
        
        Args:
            inputs: {
                'symbol': '600519',
                'stock_name': '贵州茅台',
                'financials': {
                    'revenue': ...,  # 营收
                    'profit': ...,   # 利润
                    'eps': ...,      # 每股收益
                    'pe': ...,       # 市盈率
                    'pb': ...,       # 市净率
                },
                'industry_avg': {...},  # 行业平均
            }
        """
        symbol = inputs.get('symbol', '')
        stock_name = inputs.get('stock_name', '')
        financials = inputs.get('financials', {})
        industry_avg = inputs.get('industry_avg', {})
        
        prompt = f"""请分析以下股票的基本面:

股票代码: {symbol}
股票名称: {stock_name}

财务数据:
{self._format_financials(financials)}

行业平均:
{self._format_industry_avg(industry_avg)}

请进行基本面分析并给出投资建议。"""
        
        return prompt
    
    def _format_financials(self, data: Dict) -> str:
        """格式化财务数据"""
        if not data:
            return "无数据"
        
        lines = []
        for name, value in data.items():
            if isinstance(value, (int, float)):
                if abs(value) > 1e8:
                    lines.append(f"  {name}: {value/1e8:.2f}亿")
                elif abs(value) > 1e4:
                    lines.append(f"  {name}: {value/1e4:.2f}万")
                else:
                    lines.append(f"  {name}: {value:.2f}")
            else:
                lines.append(f"  {name}: {value}")
        
        return '\n'.join(lines)
    
    def _format_industry_avg(self, data: Dict) -> str:
        """格式化行业平均"""
        if not data:
            return "无数据"
        
        lines = []
        for name, value in data.items():
            lines.append(f"  行业{name}: {value}")
        
        return '\n'.join(lines)
```

---

## 4. 研究员 (Researchers)

### 4.1 Bull Researcher (看涨研究员)

```python
# agent_integration/agents/researchers/bull_researcher.py

from typing import Dict, Any
from .base import BaseAgent, AgentConfig

class BullResearcher(BaseAgent):
    """
    看涨研究员
    
    职责:
    - 收集看涨证据
    - 构建买入论点
    - 分析催化剂因素
    - 识别上涨潜力
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "构建股票的看涨投资论点"
        if not config.backstory:
            self.config.backstory = """你是一位乐观的股票研究员，专注于寻找股票的上涨潜力。
            你善于发现被市场忽视的正面因素，
            你的分析逻辑严谨，但观点偏向多头思维。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位专业的看涨研究员。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

任务:
基于以下分析师报告，构建看涨投资论点。

要求:
1. 提炼3-5个核心看涨理由
2. 分析可能的催化剂因素
3. 评估上涨空间和目标价
4. 识别关键风险点 (但不过分强调)

输出格式:
请以结构化格式输出:
- 核心看涨理由:
  1. ...
  2. ...
  3. ...
- 催化剂: [列出可能的催化剂]
- 目标价: XXX元 (上涨空间: XX%)
- 关键风险: [简述]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入数据
        
        Args:
            inputs: {
                'symbol': '600519',
                'stock_name': '贵州茅台',
                'analyst_reports': {
                    'market': {...},   # 市场分析
                    'news': {...},     # 新闻分析
                    'fundamentals': {...},  # 基本面分析
                },
            }
        """
        symbol = inputs.get('symbol', '')
        stock_name = inputs.get('stock_name', '')
        reports = inputs.get('analyst_reports', {})
        
        reports_text = self._format_reports(reports)
        
        prompt = f"""请基于以下分析师报告，构建看涨投资论点:

股票代码: {symbol}
股票名称: {stock_name}

分析师报告汇总:
{reports_text}

请构建看涨投资论点。"""
        
        return prompt
    
    def _format_reports(self, reports: Dict) -> str:
        """格式化分析师报告"""
        lines = []
        
        for name, report in reports.items():
            lines.append(f"【{name.upper()}分析报告】")
            if isinstance(report, dict):
                for k, v in report.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"  {report}")
            lines.append("")
        
        return '\n'.join(lines)
```

### 4.2 Bear Researcher (看跌研究员)

```python
# agent_integration/agents/researchers/bear_researcher.py

from typing import Dict, Any
from .base import BaseAgent, AgentConfig

class BearResearcher(BaseAgent):
    """
    看跌研究员
    
    职责:
    - 收集看跌证据
    - 构建卖出论点
    - 分析风险因素
    - 识别下跌风险
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "构建股票的看跌投资论点"
        if not config.backstory:
            self.config.backstory = """你是一位谨慎的股票研究员，专注于识别股票的风险和问题。
            你善于发现潜在的负面因素，
            你的分析客观严谨，观点偏向空头思维。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位专业的看跌研究员。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

任务:
基于以下分析师报告，构建看跌投资论点。

要求:
1. 提炼3-5个核心看跌理由
2. 分析可能的下行风险
3. 评估下跌空间
4. 给出风险提示

输出格式:
请以结构化格式输出:
- 核心看跌理由:
  1. ...
  2. ...
  3. ...
- 下行风险: [列出风险因素]
- 目标价: XXX元 (下跌空间: XX%)
- 风险提示: [重要风险]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """与Bull Researcher类似，但角色不同"""
        symbol = inputs.get('symbol', '')
        stock_name = inputs.get('stock_name', '')
        reports = inputs.get('analyst_reports', {})
        
        reports_text = self._format_reports(reports)
        
        prompt = f"""请基于以下分析师报告，构建看跌投资论点:

股票代码: {symbol}
股票名称: {stock_name}

分析师报告汇总:
{reports_text}

请构建看跌投资论点。"""
        
        return prompt
    
    def _format_reports(self, reports: Dict) -> str:
        """格式化分析师报告"""
        lines = []
        
        for name, report in reports.items():
            lines.append(f"【{name.upper()}分析报告】")
            if isinstance(report, dict):
                for k, v in report.items():
                    lines.append(f"  {k}: {v}")
            else:
                lines.append(f"  {report}")
            lines.append("")
        
        return '\n'.join(lines)
```

---

## 5. 管理器 (Managers)

### 5.1 Research Manager (研究管理器)

```python
# agent_integration/agents/managers/research_manager.py

from typing import Dict, Any, List
from .base import BaseAgent, AgentConfig

class ResearchManager(BaseAgent):
    """
    研究管理器
    
    职责:
    - 协调研究员工作
    - 整合看涨/看跌论点
    - 做出投资决策
    - 控制辩论流程
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "协调研究流程并做出投资决策"
        if not config.backstory:
            self.config.backstory = """你是一位经验丰富的投资研究总监，
            负责协调研究团队的工作，整合各方观点，
            最终做出客观的投资决策。你不偏多也不偏空，一切以事实和数据为准。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位投资研究总监。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

任务:
整合研究员的研究成果，做出投资决策。

要求:
1. 评估看涨论点的可信度
2. 评估看跌论点的可信度
3. 综合权衡后给出最终决策
4. 决策必须是明确的 [买入/持有/卖出]

输出格式:
请以结构化格式输出:
- 决策: [买入/持有/卖出]
- 置信度: X/10
- 核心逻辑: [2-3句话总结]
- 主要看涨因素:
  1. ...
  2. ...
- 主要看跌因素:
  1. ...
  2. ...
- 风险提示: [如有]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入数据
        
        Args:
            inputs: {
                'symbol': '600519',
                'bull_research': {...},  # 看涨研究
                'bear_research': {...},  # 看跌研究
            }
        """
        symbol = inputs.get('symbol', '')
        bull_research = inputs.get('bull_research', {})
        bear_research = inputs.get('bear_research', {})
        
        prompt = f"""请基于以下研究结果，做出投资决策:

股票代码: {symbol}

【看涨研究】
{self._format_research(bull_research)}

【看跌研究】
{self._format_research(bear_research)}

请做出最终投资决策。"""
        
        return prompt
    
    def _format_research(self, research: Dict) -> str:
        """格式化研究成果"""
        if not research:
            return "无数据"
        
        lines = []
        for k, v in research.items():
            lines.append(f"  {k}: {v}")
        
        return '\n'.join(lines)
```

---

## 6. 风险辩论 (Risk Debaters)

### 6.1 Conservative Debator (保守辩论者)

```python
# agent_integration/agents/risk_mgmt/conservative_debator.py

from typing import Dict, Any
from .base import BaseAgent, AgentConfig

class ConservativeDebator(BaseAgent):
    """
    保守辩论者
    
    立场: 强调风险，倾向于安全边际
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "从保守角度评估投资风险"
        if not config.backstory:
            self.config.backstory = """你是一位极度保守的风险管理者，
            你的投资理念是"本金安全第一"。
            你总是看到最坏的情况，强调下行风险。"""
        
        self.config.role = "保守辩论者"
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位保守辩论者。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

立场:
- 强调本金安全
- 倾向于高安全边际
- 对不确定性持谨慎态度
- 偏好止损保护

任务:
对投资决策提出保守的风险评估。

输出格式:
- 风险评级: [高/中/低]
- 主要风险点:
  1. ...
  2. ...
- 安全边际评估: [充足/一般/不足]
- 建议: [如何降低风险]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        symbol = inputs.get('symbol', '')
        decision = inputs.get('decision', {})
        
        prompt = f"""请从保守角度评估以下投资决策:

股票代码: {symbol}
投资决策: {decision.get('decision', '未知')}
置信度: {decision.get('confidence', '未知')}

请进行保守风险评估。"""
        
        return prompt
```

### 6.2 Neutral Debator (中性辩论者)

```python
# agent_integration/agents/risk_mgmt/neutral_debator.py

from typing import Dict, Any
from .base import BaseAgent, AgentConfig

class NeutralDebator(BaseAgent):
    """
    中性辩论者
    
    立场: 平衡风险与收益
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "从平衡角度评估投资风险"
        if not config.backstory:
            self.config.backstory = """你是一位平衡的风险管理者，
            你的投资理念是"风险与收益对等"。
            你客观评估多空双方观点，寻求最优风险收益比。"""
        
        self.config.role = "中性辩论者"
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位中性辩论者。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

立场:
- 风险与收益平衡
- 客观评估多空双方
- 寻求最优风险收益比
- 关注概率分布

任务:
对投资决策提出中性的风险评估。

输出格式:
- 风险评级: [高/中/低]
- 多空平衡点: [分析]
- 建议: [如何优化风险收益]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        symbol = inputs.get('symbol', '')
        decision = inputs.get('decision', {})
        
        prompt = f"""请从平衡角度评估以下投资决策:

股票代码: {symbol}
投资决策: {decision.get('decision', '未知')}
置信度: {decision.get('confidence', '未知')}

请进行中性风险评估。"""
        
        return prompt
```

### 6.3 Aggressive Debator (激进辩论者)

```python
# agent_integration/agents/risk_mgmt/aggressive_debator.py

from typing import Dict, Any
from .base import BaseAgent, AgentConfig

class AggressiveDebator(BaseAgent):
    """
    激进辩论者
    
    立场: 强调机会，倾向于高收益
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "从激进角度评估投资机会"
        if not config.backstory:
            self.config.backstory = """你是一位激进的成长型投资者，
            你的投资理念是"高风险高收益"。
            你善于发现潜在的机会，敢于重仓出击。"""
        
        self.config.role = "激进辩论者"
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位激进辩论者。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

立场:
- 强调上涨机会
- 倾向于高收益
- 愿意承担更高风险
- 关注催化剂和弹性

任务:
对投资决策提出激进的机会评估。

输出格式:
- 机会评级: [高/中/低]
- 主要机会点:
  1. ...
  2. ...
- 上行空间: XX%
- 建议: [如何最大化收益]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        symbol = inputs.get('symbol', '')
        decision = inputs.get('decision', {})
        
        prompt = f"""请从激进角度评估以下投资决策:

股票代码: {symbol}
投资决策: {decision.get('decision', '未知')}
置信度: {decision.get('confidence', '未知')}

请进行激进机会评估。"""
        
        return prompt
```

---

## 7. Risk Manager (风险管理器)

```python
# agent_integration/agents/managers/risk_manager.py

from typing import Dict, Any, List
from .base import BaseAgent, AgentConfig

class RiskManager(BaseAgent):
    """
    风险管理器
    
    职责:
    - 综合辩论者意见
    - 制定风险策略
    - 确定风险参数
    - 最终风险决策
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "综合评估并制定风险管理策略"
        if not config.backstory:
            self.config.backstory = """你是一位资深的风控总监，
            负责综合各方意见，制定最终的风险管理策略。
            你的决策直接影响投资组合的安全。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位风险管理总监。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

任务:
综合三位辩论者 (保守/中性/激进) 的意见，制定风险管理策略。

要求:
1. 权衡三种观点
2. 确定最终风险评级
3. 制定具体风控措施

输出格式:
- 综合风险评级: [高/中/低]
- 风险管理策略:
  - 仓位建议: [轻仓/半仓/满仓]
  - 止损位: XXX元 (-X%)
  - 止盈位: XXX元 (+X%)
  - 持仓周期: [短线/中线/长线]
- 监控要点: [列出需要关注的风险指标]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入数据
        
        Args:
            inputs: {
                'symbol': '600519',
                'decision': {...},           # 投资决策
                'conservative_view': {...},  # 保守观点
                'neutral_view': {...},       # 中性观点
                'aggressive_view': {...},    # 激进观点
            }
        """
        symbol = inputs.get('symbol', '')
        decision = inputs.get('decision', {})
        
        conservative = inputs.get('conservative_view', {})
        neutral = inputs.get('neutral_view', {})
        aggressive = inputs.get('aggressive_view', {})
        
        prompt = f"""请综合以下辩论者意见，制定风险管理策略:

股票代码: {symbol}
投资决策: {decision.get('decision', '未知')}

【保守辩论者观点】
{self._format_view(conservative)}

【中性辩论者观点】
{self._format_view(neutral)}

【激进辩论者观点】
{self._format_view(aggressive)}

请制定综合风险管理策略。"""
        
        return prompt
    
    def _format_view(self, view: Dict) -> str:
        """格式化观点"""
        if not view:
            return "无数据"
        
        lines = []
        for k, v in view.items():
            lines.append(f"  {k}: {v}")
        
        return '\n'.join(lines)
```

---

## 8. Trader (交易员)

```python
# agent_integration/agents/trader/trader.py

from typing import Dict, Any
from .base import BaseAgent, AgentConfig

class Trader(BaseAgent):
    """
    交易员
    
    职责:
    - 生成最终交易信号
    - 确定入场点位
    - 制定交易计划
    - 风险管理执行
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        
        if not config.goal:
            self.config.goal = "生成最终交易信号"
        if not config.backstory:
            self.config.backstory = """你是一位专业交易员，
            负责将分析结论转化为具体的交易指令。
            你精通技术分析和交易心理学，能够把握最佳入场时机。"""
    
    def _create_system_prompt(self) -> str:
        return f"""你是一位专业交易员。

角色: {self.config.role}
目标: {self.config.goal}

背景: {self.config.backstory}

任务:
基于投资决策和风险管理策略，生成最终交易指令。

要求:
1. 确定具体入场点位
2. 制定交易计划
3. 设置止损止盈
4. 明确仓位管理

输出格式:
- 交易信号: [买入/卖出/观望]
- 入场点位: XXX元
- 仓位: XX%
- 止损位: XXX元 (-X%)
- 止盈位: XXX元 (+X%)
- 持仓周期: [1天/1周/1月]
- 交易理由: [简要说明]
"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """
        处理输入数据
        
        Args:
            inputs: {
                'symbol': '600519',
                'stock_name': '贵州茅台',
                'current_price': 1800.0,
                'decision': {...},    # 投资决策
                'risk_strategy': {...},  # 风险策略
            }
        """
        symbol = inputs.get('symbol', '')
        stock_name = inputs.get('stock_name', '')
        current_price = inputs.get('current_price', 0)
        decision = inputs.get('decision', {})
        risk_strategy = inputs.get('risk_strategy', {})
        
        prompt = f"""请生成最终交易指令:

股票代码: {symbol}
股票名称: {stock_name}
当前价格: {current_price}元

投资决策:
{self._format_dict(decision)}

风险管理策略:
{self._format_dict(risk_strategy)}

请生成交易指令。"""
        
        return prompt
    
    def _format_dict(self, data: Dict) -> str:
        """格式化字典数据"""
        if not data:
            return "无数据"
        
        lines = []
        for k, v in data.items():
            lines.append(f"  {k}: {v}")
        
        return '\n'.join(lines)
```

---

## 9. 目录结构

```
agent_integration/
├── __init__.py
│
├── base.py                    # BaseAgent基类
│
├── analysts/                  # 分析师
│   ├── __init__.py
│   ├── base.py              # Analyst基类
│   ├── market_analyst.py
│   ├── fundamentals_analyst.py
│   ├── news_analyst.py
│   ├── social_media_analyst.py
│   └── china_market_analyst.py
│
├── researchers/              # 研究员
│   ├── __init__.py
│   ├── base.py             # Researcher基类
│   ├── bull_researcher.py
│   └── bear_researcher.py
│
├── managers/                # 管理器
│   ├── __init__.py
│   ├── research_manager.py
│   └── risk_manager.py
│
├── risk_mgmt/              # 风险辩论
│   ├── __init__.py
│   ├── base.py           # Debator基类
│   ├── conservative_debator.py
│   ├── neutral_debator.py
│   └── aggressive_debator.py
│
└── trader/                 # 交易员
    ├── __init__.py
    └── trader.py
```

---

## 10. 使用示例

```python
from agent_integration.agents import (
    MarketAnalyst, NewsAnalyst, FundamentalsAnalyst,
    BullResearcher, BearResearcher,
    ResearchManager,
    ConservativeDebator, NeutralDebator, AggressiveDebator,
    RiskManager, Trader,
    AgentConfig
)
from agent_integration.llm_adapters import create_llm_by_provider

# 创建LLM
llm = create_llm_by_provider('deepseek', 'deepseek-chat')

# 创建分析师
market_analyst = MarketAnalyst(AgentConfig(
    name='market_analyst',
    role='市场技术分析师',
    goal='提供技术分析报告',
    llm=llm,
    verbose=True
))

# 运行分析师
market_result = market_analyst.run({
    'symbol': '600519',
    'stock_name': '贵州茅台',
    'trade_date': '2024-05-10',
    'price_data': [...],
    'indicators': {...},
})

print(market_result['output'])
```

---

## 11. 后续优化

### 11.1 短期优化

- [ ] 添加Social Media Analyst
- [ ] 添加China Market Analyst
- [ ] 实现向量记忆集成

### 11.2 中期优化

- [ ] 支持异步执行
- [ ] 添加进度回调
- [ ] 实现结果缓存

### 11.3 长期优化

- [ ] 支持多模型对比
- [ ] 实现自适应Agent选择
- [ ] 构建Agent协作工作流
