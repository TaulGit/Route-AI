"""Unsplash 图片服务 — 按POI名称搜索实景照片"""

import httpx
from typing import Optional, List
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import get_settings
from ..models.schemas import POI


class UnsplashService:
    """Unsplash 图片搜索服务"""

    def __init__(self):
        settings = get_settings()
        self.access_key = settings.unsplash_access_key
        self.enabled = bool(self.access_key and self.access_key != "your_unsplash_key")

        if self.enabled:
            print(f"[Unsplash] 已启用, Access Key: {self.access_key[:8]}...")
        else:
            print("[Unsplash] 未配置 Access Key，图片功能不可用")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def search_photo(self, query: str, city: str = "") -> Optional[str]:
        """
        搜索一张相关的照片，返回图片URL

        Args:
            query: 搜索关键词（通常是POI名称）
            city: 城市名（可选，用于提高准确性）

        Returns:
            图片URL，未找到返回None
        """
        if not self.enabled:
            return None

        # 加上城市名提高匹配度
        full_query = f"{query} {city}" if city else query

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.unsplash.com/search/photos",
                    params={
                        "query": full_query,
                        "per_page": 1,
                        "orientation": "landscape",
                        "client_id": self.access_key
                    }
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if results:
                url = results[0]["urls"]["regular"]
                print(f"[Unsplash] 找到图片: {query} -> {url[:60]}...")
                return url

            # 去掉城市名再试一次
            if city:
                return await self._search_without_city(query)

            print(f"[Unsplash] 未找到图片: {query}")
            return None

        except Exception as e:
            print(f"[Unsplash] 搜索失败: {query} - {e}")
            return None

    async def _search_without_city(self, query: str) -> Optional[str]:
        """不带城市名搜索（fallback）"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.unsplash.com/search/photos",
                    params={
                        "query": query,
                        "per_page": 1,
                        "orientation": "landscape",
                        "client_id": self.access_key
                    }
                )
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if results:
                url = results[0]["urls"]["regular"]
                print(f"[Unsplash] 兜底找到: {query} -> {url[:60]}...")
                return url
        except Exception:
            pass
        return None

    async def enrich_pois(self, pois: List[POI], city: str) -> List[POI]:
        """
        批量为POI搜索图片

        Args:
            pois: POI列表
            city: 城市名

        Returns:
            带有image_url的POI列表
        """
        if not self.enabled:
            return pois

        import asyncio
        semaphore = asyncio.Semaphore(5)

        async def enrich_one(poi: POI) -> POI:
            if poi.image_url:
                return poi

            async with semaphore:
                url = await self.search_photo(poi.name, city)
                if url:
                    poi.image_url = url
            return poi

        tasks = [enrich_one(p) for p in pois]
        enriched = await asyncio.gather(*tasks)

        with_images = sum(1 for p in enriched if p.image_url)
        print(f"[Unsplash] 批量完成: {with_images}/{len(enriched)} 个POI有图片")

        return list(enriched)


# 单例
_unsplash_service: Optional[UnsplashService] = None


def get_unsplash_service() -> UnsplashService:
    global _unsplash_service
    if _unsplash_service is None:
        _unsplash_service = UnsplashService()
    return _unsplash_service
