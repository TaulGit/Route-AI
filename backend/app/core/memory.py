"""记忆系统模块 - 支持对话记忆和用户偏好存储"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from .config import get_settings


class ConversationMemory:
    """对话记忆管理"""

    def __init__(self, session_id: str, user_id: Optional[str] = None, max_history: int = 10):
        """
        初始化对话记忆

        Args:
            session_id: 会话 ID
            user_id: 用户 ID（用于个性化持久化）
            max_history: 最大历史消息数
        """
        self.session_id = session_id
        self.user_id = user_id
        self.max_history = max_history
        self._history: List[BaseMessage] = []
        self._user_preferences: Dict[str, Any] = {}
        self._created_at = datetime.now()

    def add_message(self, message: BaseMessage) -> None:
        """添加消息到历史"""
        self._history.append(message)
        # 保持历史记录在限制内
        if len(self._history) > self.max_history * 2:
            self._history = self._history[-self.max_history * 2:]

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.add_message(HumanMessage(content=content))

    def add_ai_message(self, content: str) -> None:
        """添加 AI 消息"""
        self.add_message(AIMessage(content=content))

    def get_history(self) -> List[BaseMessage]:
        """获取对话历史"""
        return self._history.copy()

    def get_history_str(self) -> str:
        """获取对话历史的字符串表示"""
        lines = []
        for msg in self._history:
            role = "用户" if isinstance(msg, HumanMessage) else "助手"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)

    def set_preference(self, key: str, value: Any) -> None:
        """设置用户偏好"""
        self._user_preferences[key] = value

    def get_preference(self, key: str, default: Any = None) -> Any:
        """获取用户偏好"""
        return self._user_preferences.get(key, default)

    def get_all_preferences(self) -> Dict[str, Any]:
        """获取所有用户偏好"""
        return self._user_preferences.copy()

    def clear(self) -> None:
        """清空记忆"""
        self._history.clear()

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "history": [
                {"role": "user" if isinstance(m, HumanMessage) else "ai", "content": m.content}
                for m in self._history
            ],
            "preferences": self._user_preferences
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMemory":
        """从字典反序列化"""
        memory = cls(data["session_id"], data.get("user_id"))
        for msg in data.get("history", []):
            if msg["role"] == "user":
                memory.add_user_message(msg["content"])
            else:
                memory.add_ai_message(msg["content"])
        memory._user_preferences = data.get("preferences", {})
        return memory

    async def persist_to_chromadb(self) -> bool:
        """将偏好持久化到ChromaDB"""
        if not self.user_id:
            return False

        try:
            from ..services.preference_service import get_preference_service
            pref_service = get_preference_service()
            profile = await pref_service.get_user_profile(self.user_id)
            if profile:
                # 更新现有画像的偏好类别
                for key, value in self._user_preferences.items():
                    if isinstance(value, (int, float)) and key in profile.preferred_categories:
                        profile.preferred_categories[key] = float(value)
                profile.last_updated = datetime.now()
                await pref_service.save_user_profile(profile)
                print(f"[Memory] 偏好已同步到ChromaDB: user={self.user_id}")
                return True
        except Exception as e:
            print(f"[Memory] ChromaDB同步失败: {e}")

        return False

    async def load_from_chromadb(self) -> bool:
        """从ChromaDB加载用户偏好"""
        if not self.user_id:
            return False

        try:
            from ..services.preference_service import get_preference_service
            pref_service = get_preference_service()
            profile = await pref_service.get_user_profile(self.user_id)
            if profile:
                self._user_preferences.update(profile.preferred_categories)
                self.set_preference("budget_preference", profile.budget_preference)
                self.set_preference("transport_preference", profile.transport_preference)
                self.set_preference("visit_history", profile.visit_history)
                print(f"[Memory] 已从ChromaDB加载偏好: user={self.user_id}")
                return True
        except Exception as e:
            print(f"[Memory] ChromaDB加载失败: {e}")

        return False


class MemoryManager:
    """记忆管理器 - 管理多个会话的记忆"""

    _instance = None
    _memories: Dict[str, ConversationMemory] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_memory(self, session_id: str, user_id: Optional[str] = None) -> ConversationMemory:
        """获取或创建会话记忆"""
        if session_id not in self._memories:
            memory = ConversationMemory(session_id, user_id=user_id)
            self._memories[session_id] = memory
            # 异步加载ChromaDB偏好（fire-and-forget）
            if user_id:
                import asyncio
                try:
                    asyncio.create_task(memory.load_from_chromadb())
                except RuntimeError:
                    # 没有事件循环时使用同步方式
                    pass
        return self._memories[session_id]

    def clear_memory(self, session_id: str) -> None:
        """清空指定会话的记忆"""
        if session_id in self._memories:
            self._memories[session_id].clear()

    def remove_session(self, session_id: str) -> None:
        """移除会话"""
        if session_id in self._memories:
            del self._memories[session_id]

    def get_all_sessions(self) -> List[str]:
        """获取所有会话 ID"""
        return list(self._memories.keys())


def get_memory_manager() -> MemoryManager:
    """获取记忆管理器单例"""
    return MemoryManager()
