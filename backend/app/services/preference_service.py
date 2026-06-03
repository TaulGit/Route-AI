"""用户偏好服务 — 用户画像的CRUD操作，基于ChromaDB持久化"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.schemas import UserProfile
from .embedding_service import get_vector_store


class PreferenceService:
    """用户偏好管理服务"""

    def __init__(self):
        self.vector_store = get_vector_store()
        # 内存缓存用户画像
        self._profile_cache: Dict[str, UserProfile] = {}

    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        if not user_id:
            return None

        # 检查内存缓存
        if user_id in self._profile_cache:
            return self._profile_cache[user_id]

        # 从ChromaDB加载
        try:
            docs = await self.vector_store.get_user_preferences(
                user_id=user_id,
                preference_type="user_profile"
            )
            if docs and len(docs) > 0:
                # 取最新的doc
                doc = docs[0]
                profile_data = json.loads(doc.page_content) if doc.page_content else {}
                profile = UserProfile(
                    user_id=user_id,
                    preferred_categories=profile_data.get("preferred_categories", {}),
                    budget_preference=profile_data.get("budget_preference", "moderate"),
                    transport_preference=profile_data.get("transport_preference", "公共交通"),
                    visit_history=profile_data.get("visit_history", []),
                    review_sentiment_preferences=profile_data.get("review_sentiment_preferences", {}),
                    preferred_poi_ids=profile_data.get("preferred_poi_ids", []),
                    avoided_poi_ids=profile_data.get("avoided_poi_ids", []),
                    last_updated=datetime.now(),
                    created_at=doc.metadata.get("created_at", datetime.now().isoformat())
                )
                self._profile_cache[user_id] = profile
                return profile
        except Exception as e:
            print(f"[PreferenceService] 加载用户画像失败: {e}")

        # 返回默认画像
        return self._create_default_profile(user_id)

    async def save_user_profile(self, profile: UserProfile) -> bool:
        """保存用户画像"""
        if not profile.user_id:
            return False

        profile.last_updated = datetime.now()
        self._profile_cache[profile.user_id] = profile

        profile_data = {
            "preferred_categories": profile.preferred_categories,
            "budget_preference": profile.budget_preference,
            "transport_preference": profile.transport_preference,
            "visit_history": profile.visit_history,
            "review_sentiment_preferences": profile.review_sentiment_preferences,
            "preferred_poi_ids": profile.preferred_poi_ids,
            "avoided_poi_ids": profile.avoided_poi_ids
        }

        try:
            await self.vector_store.save_user_preference(
                user_id=profile.user_id,
                preference_type="user_profile",
                preference_data=profile_data
            )
            print(f"[PreferenceService] 用户画像已保存: {profile.user_id}")
            return True
        except Exception as e:
            print(f"[PreferenceService] 保存用户画像失败: {e}")
            return False

    async def update_after_trip(
        self,
        user_id: str,
        visited_pois: List[str],
        preferences_used: List[str],
        budget_used: int,
        feedback: Optional[str] = None
    ) -> Optional[UserProfile]:
        """行程完成后更新用户偏好"""
        if not user_id:
            return None

        profile = await self.get_user_profile(user_id)
        if not profile:
            profile = self._create_default_profile(user_id)

        # 更新访问历史
        for poi_name in visited_pois:
            if poi_name not in profile.visit_history:
                profile.visit_history.append(poi_name)
        # 限制历史长度
        if len(profile.visit_history) > 100:
            profile.visit_history = profile.visit_history[-100:]

        # 更新偏好类别权重
        for pref in preferences_used:
            current = profile.preferred_categories.get(pref, 0)
            profile.preferred_categories[pref] = min(1.0, current + 0.1)

        # 衰减其他类别
        for key in profile.preferred_categories:
            if key not in preferences_used:
                profile.preferred_categories[key] = max(0.0, profile.preferred_categories[key] - 0.02)

        # 更新预算偏好
        if budget_used < 200:
            profile.budget_preference = "economy"
        elif budget_used < 500:
            profile.budget_preference = "moderate"
        else:
            profile.budget_preference = "luxury"

        await self.save_user_profile(profile)
        return profile

    async def update_preference_weight(
        self,
        user_id: str,
        category: str,
        delta: float
    ) -> Optional[UserProfile]:
        """调整单个偏好类别的权重"""
        if not user_id:
            return None

        profile = await self.get_user_profile(user_id)
        if not profile:
            profile = self._create_default_profile(user_id)

        current = profile.preferred_categories.get(category, 0)
        profile.preferred_categories[category] = max(0.0, min(1.0, current + delta))

        await self.save_user_profile(profile)
        return profile

    def _create_default_profile(self, user_id: str) -> UserProfile:
        """创建默认用户画像"""
        return UserProfile(
            user_id=user_id,
            preferred_categories={
                "历史文化": 0.3,
                "自然风光": 0.3,
                "美食": 0.3,
                "购物": 0.2,
                "艺术": 0.2,
                "休闲": 0.3
            },
            budget_preference="moderate",
            transport_preference="公共交通",
            visit_history=[],
            review_sentiment_preferences={},
            preferred_poi_ids=[],
            avoided_poi_ids=[],
            created_at=datetime.now()
        )

    async def get_personalized_preferences(
        self,
        user_id: str,
        explicit_preferences: List[str]
    ) -> List[str]:
        """
        合并用户显式偏好和历史偏好

        返回加权的偏好关键词列表
        """
        if not user_id:
            return explicit_preferences

        profile = await self.get_user_profile(user_id)
        if not profile:
            return explicit_preferences

        # 合并显式偏好和历史偏好
        merged = list(explicit_preferences) if explicit_preferences else []

        # 从历史偏好中提取高分类别
        for category, weight in sorted(
            profile.preferred_categories.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if weight > 0.3 and category not in merged:
                merged.append(category)

        print(f"[PreferenceService] 个性化偏好合并: 显式{explicit_preferences} + 历史{merged}")
        return merged[:5]  # 最多返回5个


# 单例
_preference_service: Optional[PreferenceService] = None


def get_preference_service() -> PreferenceService:
    global _preference_service
    if _preference_service is None:
        _preference_service = PreferenceService()
    return _preference_service
