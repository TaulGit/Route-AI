"""点评评价服务 — LLM生成UGC评价 + ChromaDB缓存 + 热度/排队估算"""

import json
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..models.schemas import POI, Review
from .embedding_service import get_vector_store
from ..core.llm import get_llm


class ReviewService:
    """评价服务 — 模拟大众点评UGC数据"""

    def __init__(self):
        self.vector_store = get_vector_store()
        self._review_cache: Dict[str, List[Review]] = {}  # 内存缓存

    def _make_cache_key(self, city: str, poi_name: str) -> str:
        """生成缓存键"""
        raw = f"{city}:{poi_name}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    async def get_poi_reviews(
        self,
        city: str,
        poi_name: str,
        poi_category: str = "",
        llm_provider: str = "deepseek"
    ) -> List[Review]:
        """获取POI的评价列表（优先缓存，没有则生成）"""
        cache_key = self._make_cache_key(city, poi_name)

        # 1. 检查内存缓存
        if cache_key in self._review_cache:
            return self._review_cache[cache_key]

        # 2. 检查ChromaDB缓存
        try:
            docs = await self.vector_store.search_similar_pois(
                query=f"评价 {poi_name}",
                city=city,
                k=3
            )
            for doc in docs:
                if doc.metadata.get("name") == poi_name and doc.metadata.get("has_reviews"):
                    reviews_raw = doc.metadata.get("reviews_json", "[]")
                    try:
                        reviews = [Review(**r) for r in json.loads(reviews_raw)]
                        if reviews:
                            self._review_cache[cache_key] = reviews
                            return reviews
                    except:
                        pass
        except Exception as e:
            print(f"[ReviewService] ChromaDB查询失败: {e}")

        # 3. 调用LLM生成模拟评价
        print(f"[ReviewService] 为 {poi_name} 生成模拟评价...")
        reviews = await self._generate_reviews(poi_name, poi_category, city, llm_provider)

        # 4. 缓存到内存和ChromaDB
        if reviews:
            self._review_cache[cache_key] = reviews
            try:
                reviews_json = json.dumps([r.model_dump() for r in reviews], ensure_ascii=False)
                await self.vector_store.add_poi_knowledge(
                    city=city,
                    pois=[{
                        "id": cache_key,
                        "name": poi_name,
                        "category": poi_category,
                        "address": city,
                        "description": f"UGC评价({len(reviews)}条)",
                        "location": {"longitude": 0, "latitude": 0},
                        "has_reviews": True,
                        "reviews_json": reviews_json,
                        "avg_rating": sum(r.rating for r in reviews) / len(reviews),
                        "review_count": len(reviews)
                    }]
                )
            except Exception as e:
                print(f"[ReviewService] 缓存评价到ChromaDB失败: {e}")

        return reviews

    async def enrich_pois_with_reviews(
        self,
        pois: List[POI],
        city: str,
        llm_provider: str = "deepseek",
        max_concurrent: int = 5
    ) -> List[POI]:
        """为POI列表批量加载/生成评价，更新热度分和排队时间"""
        import asyncio

        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_one(poi: POI) -> POI:
            async with semaphore:
                try:
                    reviews = await self.get_poi_reviews(
                        city=city,
                        poi_name=poi.name,
                        poi_category=poi.category or "",
                        llm_provider=llm_provider
                    )
                    if reviews:
                        # 计算热度分
                        avg_rating = sum(r.rating for r in reviews) / len(reviews)
                        like_total = sum(r.like_count for r in reviews)
                        poi.popularity_score = min(100, avg_rating * 15 + like_total * 0.5 + len(reviews) * 3)

                        # 估算排队时间（基于评价中的"排队"标签）
                        queue_tags = sum(1 for r in reviews for t in r.tags if "排队" in t)
                        negative_queue = sum(1 for r in reviews for t in r.tags if "排队久" in t or "排队慢" in t)
                        if queue_tags > 0:
                            base_queue = queue_tags * 5 + negative_queue * 10
                            poi.queue_time_min = min(60, max(0, base_queue))
                        else:
                            poi.queue_time_min = 0

                        # 用平均评分更新POI评分
                        if not poi.rating:
                            poi.rating = round(avg_rating, 1)

                        print(f"[ReviewService] {poi.name}: 评分={avg_rating:.1f}, 热度={poi.popularity_score:.0f}, 排队={poi.queue_time_min}min")
                except Exception as e:
                    print(f"[ReviewService] 处理 {poi.name} 评价失败: {e}")

            return poi

        tasks = [enrich_one(p) for p in pois]
        enriched = await asyncio.gather(*tasks)
        return list(enriched)

    async def _generate_reviews(
        self,
        poi_name: str,
        poi_category: str,
        city: str,
        llm_provider: str = "deepseek"
    ) -> List[Review]:
        """使用LLM生成模拟的大众点评风格评价"""
        prompt = f"""你是一个大众点评用户。请为「{poi_name}」({poi_category})生成3条真实的用户评价。

要求:
- 城市: {city}
- 每条评价有具体的体验细节（如菜品/环境/服务/排队/价格）
- 评分1-5分，至少有一条4分以上，至少有一条提到排队情况
- 评价内容30-80字，真实自然，有口语化表达
- 标签选择: 排队快/排队久/性价比高/环境好/服务好/味道赞/分量足/适合打卡/老字号/网红店 中选2-4个

返回纯JSON数组格式，不要markdown代码块:
[
  {{"user_name": "用户昵称", "rating": 4.5, "content": "评价内容", "sentiment": "positive", "tags": ["标签1", "标签2"], "like_count": 点赞数, "date": "2026-05-15"}},
  ...
]"""

        try:
            llm = get_llm(llm_provider, temperature=0.8, max_tokens=800)
            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # 提取JSON
            import re
            match = re.search(r'\[[\s\S]*\]', content)
            if match:
                data = json.loads(match.group())
                reviews = []
                for item in data:
                    reviews.append(Review(
                        poi_name=poi_name,
                        user_name=item.get("user_name", "匿名用户"),
                        rating=item.get("rating", 4.0),
                        content=item.get("content", ""),
                        sentiment=item.get("sentiment", "neutral"),
                        tags=item.get("tags", []),
                        like_count=item.get("like_count", 0),
                        date=item.get("date", datetime.now().strftime("%Y-%m-%d"))
                    ))
                print(f"[ReviewService] 为 {poi_name} 生成了 {len(reviews)} 条评价")
                return reviews
        except Exception as e:
            print(f"[ReviewService] LLM生成评价失败: {e}")

        # 失败时返回空列表
        return []

    def calculate_popularity(self, reviews: List[Review]) -> float:
        """根据评价计算热度分(0-100)"""
        if not reviews:
            return 30.0

        avg_rating = sum(r.rating for r in reviews) / len(reviews)
        like_total = sum(r.like_count for r in reviews)
        positive_ratio = sum(1 for r in reviews if r.sentiment == "positive") / len(reviews)

        score = avg_rating * 12 + like_total * 0.3 + positive_ratio * 20 + len(reviews) * 2
        return min(100, max(0, score))

    def estimate_queue_time(self, reviews: List[Review], popularity: float) -> int:
        """根据评价估算排队时间(分钟)"""
        if not reviews:
            return 0

        # 统计排队相关标签
        queue_mentions = 0
        negative_queue = 0
        for r in reviews:
            for tag in r.tags:
                if "排队" in tag:
                    queue_mentions += 1
                    if "久" in tag or "慢" in tag:
                        negative_queue += 1

        if queue_mentions == 0 and popularity > 70:
            # 热度高但无人提排队 -> 可能不太需要排队
            base = 5
        elif queue_mentions == 0:
            base = 0
        else:
            base = queue_mentions * 8 + negative_queue * 12

        # 热度修正
        popularity_bonus = (popularity - 50) * 0.3 if popularity > 50 else 0

        return min(120, max(0, int(base + popularity_bonus)))


# 单例
_review_service: Optional[ReviewService] = None


def get_review_service() -> ReviewService:
    global _review_service
    if _review_service is None:
        _review_service = ReviewService()
    return _review_service
