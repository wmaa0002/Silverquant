"""
新闻分析师 - NewsAnalyst实现
"""
from typing import Dict, Any, List, Optional

from agent_integration.agents.base import BaseAgent, AgentConfig
from agent_integration.dataflows.news.base import NewsItem


class NewsAnalyst(BaseAgent):
    """新闻分析师智能体
    
    负责分析新闻事件对股价的影响。
    """
    
    def __init__(self, config: AgentConfig):
        """初始化新闻分析师"""
        super().__init__(config)
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return """你是A股市场新闻分析师，专注于分析新闻事件对股价的影响。

你的职责：
1. 分析新闻对股价的潜在影响（正面、负面、中性）
2. 评估新闻的重要程度（重大、 一般、轻微）
3. 判断新闻的时效性（短期影响、长期影响）
4. 结合市场整体环境分析新闻影响
5. 识别新闻背后的投资机会或风险

分析要求：
- 客观评估新闻，不带主观偏见
- 区分事实和观点
- 关注新闻的具体细节和数据
- 提示投资风险

请用简洁专业的语言输出分析结果。"""
    
    def _process_input(self, inputs: Dict[str, Any]) -> str:
        """处理输入数据"""
        task = inputs.get('task', 'analyze')
        
        if task == 'analyze_news':
            news_item = inputs.get('news_item')
            if news_item:
                return self._format_single_news(news_item)
        
        elif task == 'summarize':
            news_list = inputs.get('news_list', [])
            stock_code = inputs.get('stock_code', '')
            return self._format_news_list(news_list, stock_code)
        
        elif task == 'sentiment':
            stock_code = inputs.get('stock_code', '')
            sentiment_data = inputs.get('sentiment_data', {})
            return self._format_sentiment(stock_code, sentiment_data)
        
        # 默认：直接处理news
        news_item = inputs.get('news_item')
        if news_item:
            return self._format_single_news(news_item)
        
        news_list = inputs.get('news_list', [])
        stock_code = inputs.get('stock_code', '')
        if news_list:
            return self._format_news_list(news_list, stock_code)
        
        return "请提供新闻数据进行分析"
    
    def _format_single_news(self, news_item: Any) -> str:
        """格式化单条新闻"""
        if isinstance(news_item, NewsItem):
            return f"""【新闻分析任务】

标题: {news_item.title}
内容: {news_item.content}
发布时间: {news_item.published_at}
来源: {news_item.source}
关联股票: {', '.join(news_item.stock_codes) if news_item.stock_codes else '无'}

请分析这条新闻对股价的影响。"""
        
        if isinstance(news_item, dict):
            title = news_item.get('title', '')
            content = news_item.get('content', news_item.get('新闻内容', ''))
            published_at = news_item.get('published_at', news_item.get('发布时间', ''))
            source = news_item.get('source', news_item.get('来源', ''))
            stock_codes = news_item.get('stock_codes', [])
            
            return f"""【新闻分析任务】

标题: {title}
内容: {content}
发布时间: {published_at}
来源: {source}
关联股票: {', '.join(stock_codes) if stock_codes else '无'}

请分析这条新闻对股价的影响。"""
        
        return str(news_item)
    
    def _format_news_list(self, news_list: List, stock_code: str = '') -> str:
        """格式化新闻列表"""
        lines = ["【新闻汇总分析任务】\n"]
        
        if stock_code:
            lines.append(f"股票代码: {stock_code}\n")
        
        lines.append(f"新闻数量: {len(news_list)}\n\n")
        
        for i, news in enumerate(news_list[:10], 1):  # 最多处理10条
            if isinstance(news, NewsItem):
                title = news.title
                content = news.content[:200] + '...' if len(news.content) > 200 else news.content
                published_at = news.published_at
                sentiment = news.sentiment.value if news.sentiment else '未分析'
            elif isinstance(news, dict):
                title = news.get('title', news.get('新闻标题', ''))
                content = news.get('content', news.get('新闻内容', ''))
                content = content[:200] + '...' if len(content) > 200 else content
                published_at = news.get('published_at', news.get('发布时间', ''))
                sentiment = news.get('sentiment', '未分析')
            else:
                title = str(news)
                content = ''
                published_at = ''
                sentiment = '未分析'
            
            lines.append(f"--- 新闻 {i} ---")
            lines.append(f"标题: {title}")
            lines.append(f"发布时间: {published_at}")
            lines.append(f"情感: {sentiment}")
            if content:
                lines.append(f"内容摘要: {content}")
            lines.append("")
        
        lines.append("请汇总分析以上新闻对股价的整体影响。")
        
        return "\n".join(lines)
    
    def _format_sentiment(self, stock_code: str, sentiment_data: Dict) -> str:
        """格式化情感数据"""
        lines = ["【情感分析任务】\n"]
        lines.append(f"股票代码: {stock_code}\n")
        
        if sentiment_data:
            total = sentiment_data.get('total', 0)
            positive = sentiment_data.get('positive', 0)
            negative = sentiment_data.get('negative', 0)
            neutral = sentiment_data.get('neutral', 0)
            avg_score = sentiment_data.get('avg_score', 0.0)
            
            lines.append(f"新闻总数: {total}")
            lines.append(f"正面新闻: {positive}")
            lines.append(f"负面新闻: {negative}")
            lines.append(f"中性新闻: {neutral}")
            lines.append(f"平均情感得分: {avg_score:.2f}")
        else:
            lines.append("无情感数据")
        
        lines.append("\n请分析该股票的整体情感倾向。")
        
        return "\n".join(lines)
    
    def analyze_news_impact(self, news_item: Dict[str, Any]) -> Dict[str, Any]:
        """分析单条新闻影响
        
        Args:
            news_item: 新闻数据
            
        Returns:
            影响分析结果
        """
        return self.run({
            'task': 'analyze_news',
            'news_item': news_item
        })
    
    def analyze_sentiment(self, stock_code: str, sentiment_data: Dict = None) -> Dict[str, Any]:
        """分析整体情感
        
        Args:
            stock_code: 股票代码
            sentiment_data: 情感数据
            
        Returns:
            情感分析结果
        """
        return self.run({
            'task': 'sentiment',
            'stock_code': stock_code,
            'sentiment_data': sentiment_data or {}
        })
    
    def summarize_news(self, news_list: List, stock_code: str = '') -> Dict[str, Any]:
        """汇总新闻要点
        
        Args:
            news_list: 新闻列表
            stock_code: 股票代码
            
        Returns:
            汇总结果
        """
        return self.run({
            'task': 'summarize',
            'news_list': news_list,
            'stock_code': stock_code
        })
    
    def analyze_news_items(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """分析NewsItem列表
        
        Args:
            news_items: NewsItem对象列表
            
        Returns:
            分析结果
        """
        return self.run({
            'news_list': news_items
        })