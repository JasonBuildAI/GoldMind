"""新闻服务"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.news import GoldNews, SentimentType
import feedparser


class NewsService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_news(self, limit: int = 20, source: str = None, sentiment: str = None) -> List[GoldNews]:
        query = self.db.query(GoldNews)
        
        if source:
            query = query.filter(GoldNews.source == source)
        
        if sentiment:
            query = query.filter(GoldNews.sentiment == sentiment)
        
        return query.order_by(GoldNews.published_at.desc()).limit(limit).all()
    
    def get_news_by_id(self, news_id: int) -> Optional[GoldNews]:
        return self.db.query(GoldNews).filter(GoldNews.id == news_id).first()
    
    def get_sentiment_summary(self) -> Dict[str, int]:
        stats = self.db.query(
            GoldNews.sentiment,
            func.count(GoldNews.id)
        ).group_by(GoldNews.sentiment).all()
        
        return {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            **{s[0].value: s[1] for s in stats}
        }
    
    def fetch_from_rss(self, rss_url: str, source: str, limit: int = 10) -> List[Dict]:
        try:
            feed = feedparser.parse(rss_url)
            
            news_list = []
            for entry in feed.entries[:limit]:
                news_list.append({
                    'title': entry.title,
                    'summary': entry.get('summary', ''),
                    'link': entry.link,
                    'published_at': entry.get('published', ''),
                    'source': source
                })
            
            return news_list
        except Exception as e:
            print(f"RSS获取失败 {source}: {e}")
            return []
    
    def fetch_all_rss_news(self) -> List[Dict]:
        all_news = []
        
        rss_sources = [
            ('http://finance.sina.com.cn/roll/finance_gold/index.d.html', '新浪财经'),
            ('http://www.fx168.com/rss/gold.xml', 'FX168'),
        ]
        
        for rss_url, source in rss_sources:
            try:
                news = self.fetch_from_rss(rss_url, source, limit=5)
                all_news.extend(news)
            except Exception as e:
                print(f"RSS获取失败 {source}: {e}")
        
        return all_news
    
    def save_news(self, news_data: Dict):
        try:
            existing = self.db.query(GoldNews).filter(
                GoldNews.url == news_data.get('url')
            ).first()
            
            if existing:
                return existing
            
            news = GoldNews(
                title=news_data['title'],
                content=news_data.get('content'),
                source=news_data.get('source'),
                url=news_data.get('url'),
                published_at=news_data.get('published_at'),
                sentiment=SentimentType.NEUTRAL,
                keywords=news_data.get('keywords')
            )
            
            self.db.add(news)
            self.db.commit()
            
            return news
        except Exception as e:
            self.db.rollback()
            print(f"保存新闻失败: {e}")
            return None
