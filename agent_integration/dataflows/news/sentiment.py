"""
情感分析器 - SentimentAnalyzer实现
"""
from typing import List, Tuple, Dict, Any
import re

from agent_integration.dataflows.news.base import NewsItem, Sentiment


class SentimentAnalyzer:
    """新闻情感分析器
    
    基于词典的情感分析，不依赖LLM。
    """
    
    POSITIVE_WORDS = [
        '上涨', '涨停', '突破', '增长', '超预期', '利好', '买入', '增持', '推荐', '大涨',
        '盈利', '利润', '业绩', '增长', '上升', '回升', '反弹', '创新高', '强势', '看好',
        '低估', '价值', '机会', '布局', '加仓', '抄底', '多头', '牛市', '景气', '复苏',
    ]
    
    NEGATIVE_WORDS = [
        '下跌', '跌停', '亏损', '风险', '暴雷', '利空', '卖出', '减持', '警告', '大跌',
        '亏损', '赔钱', '业绩下滑', '下降', '回落', '调整', '创新低', '弱势', '看空',
        '高估', '泡沫', '出逃', '减仓', '割肉', '空头', '熊市', '衰退', '危机', '风险',
    ]
    
    INTENSIFIERS = ['大幅', '明显', '显著', '持续', '强劲', '严重']
    NEGATORS = ['不', '无', '非', '未', '没有', '不是']
    
    def __init__(self, use_llm: bool = False, llm_adapter=None):
        """初始化情感分析器
        
        Args:
            use_llm: 是否使用LLM进行情感分析
            llm_adapter: LLM适配器实例
        """
        self.use_llm = use_llm
        self.llm_adapter = llm_adapter
        self.positive_set = set(self.POSITIVE_WORDS)
        self.negative_set = set(self.NEGATIVE_WORDS)
    
    def analyze(self, news_item: NewsItem) -> Sentiment:
        """分析单条新闻情感
        
        Args:
            news_item: 新闻对象
            
        Returns:
            情感分类
        """
        text = news_item.title + ' ' + news_item.content
        sentiment, _ = self.analyze_text(text)
        return sentiment
    
    def analyze_text(self, text: str) -> Tuple[Sentiment, float]:
        """直接分析文本情感
        
        Args:
            text: 文本内容
            
        Returns:
            (Sentiment, score) - score范围 [-1.0, 1.0]
        """
        # 如果启用LLM且有适配器，使用LLM分析
        if self.use_llm and self.llm_adapter:
            return self._analyze_with_llm(text)
        
        score = self._calculate_score(text)
        
        if score > 0.1:
            return Sentiment.POSITIVE, score
        elif score < -0.1:
            return Sentiment.NEGATIVE, score
        else:
            return Sentiment.NEUTRAL, score
    
    def _calculate_score(self, text: str) -> float:
        """计算情感得分
        
        Args:
            text: 文本内容
            
        Returns:
            情感得分 [-1.0, 1.0]
        """
        if not text:
            return 0.0
        
        text = text.lower()
        words = self._tokenize(text)
        
        positive_count = 0
        negative_count = 0
        
        for word in self.positive_set:
            if word in text:
                positive_count += 1
                # 检查是否有强化词
                for intensifier in self.INTENSIFIERS:
                    if intensifier + word in text:
                        positive_count += 0.5
        
        for word in self.negative_set:
            if word in text:
                negative_count += 1
                for intensifier in self.INTENSIFIERS:
                    if intensifier + word in text:
                        negative_count += 0.5
        
        # 检查否定词
        for negator in self.NEGATORS:
            if negator in text:
                # 简单处理：否定词后的情感词反转
                idx = text.find(negator)
                remaining = text[idx:]
                for word in self.positive_set:
                    if word in remaining:
                        positive_count -= 0.5
                        negative_count += 0.5
                for word in self.negative_set:
                    if word in remaining:
                        negative_count -= 0.5
                        positive_count += 0.5
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        # 计算标准化得分
        raw_score = (positive_count - negative_count) / (positive_count + negative_count)
        
        # 限制在 [-1.0, 1.0] 范围内
        return max(-1.0, min(1.0, raw_score))
    
    def _analyze_with_llm(self, text: str) -> Tuple[Sentiment, float]:
        """使用LLM进行情感分析"""
        if self.llm_adapter is None:
            return self._calculate_score(text)
        
        prompt = f"""分析以下文本的情感倾向，返回JSON格式：
{{"sentiment": "positive"或"negative"或"neutral", "score": -1.0到1.0之间的分数}}
文本：{text[:500]}"""
        
        response = self.llm_adapter.chat([
            {'role': 'user', 'content': prompt}
        ])
        
        # 解析JSON响应
        try:
            import json
            result = json.loads(response)
            sentiment_str = result.get('sentiment', 'neutral')
            score = float(result.get('score', 0.0))
            
            sentiment_map = {
                'positive': Sentiment.POSITIVE,
                'negative': Sentiment.NEGATIVE,
                'neutral': Sentiment.NEUTRAL
            }
            return sentiment_map.get(sentiment_str, Sentiment.NEUTRAL), score
        except:
            return Sentiment.NEUTRAL, 0.0
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词
        
        Args:
            text: 文本
            
        Returns:
            词列表
        """
        return re.findall(r'[\u4e00-\u9fff]+', text)
    
    def batch_analyze(self, news_list: List[NewsItem]) -> List[Dict[str, Any]]:
        """批量分析新闻情感
        
        Args:
            news_list: 新闻列表
            
        Returns:
            带情感标签的新闻列表
        """
        results = []
        for news in news_list:
            sentiment, score = self.analyze_text(news.title + ' ' + news.content)
            news.sentiment = sentiment
            
            results.append({
                'news': news,
                'sentiment': sentiment,
                'score': score,
            })
        
        return results
    
    def get_sentiment_summary(self, news_list: List[NewsItem]) -> Dict[str, Any]:
        """获取情感分析摘要
        
        Args:
            news_list: 新闻列表
            
        Returns:
            情感分析摘要
        """
        if not news_list:
            return {
                'total': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'avg_score': 0.0,
            }
        
        batch_results = self.batch_analyze(news_list)
        
        positive = sum(1 for r in batch_results if r['sentiment'] == Sentiment.POSITIVE)
        negative = sum(1 for r in batch_results if r['sentiment'] == Sentiment.NEGATIVE)
        neutral = sum(1 for r in batch_results if r['sentiment'] == Sentiment.NEUTRAL)
        
        scores = [r['score'] for r in batch_results]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        return {
            'total': len(news_list),
            'positive': positive,
            'negative': negative,
            'neutral': neutral,
            'avg_score': avg_score,
            'positive_ratio': positive / len(news_list),
            'negative_ratio': negative / len(news_list),
        }