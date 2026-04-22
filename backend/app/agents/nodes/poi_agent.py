"""POI 搜索 Agent 节点"""

from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

from ...core.llm import get_llm
from ...services.amap_service import get_amap_service
from ...models.schemas import AgentState, AgentStep, NodeType, TripStatus


# POI 搜索 Agent 的系统提示
POI_AGENT_PROMPT = """你是一个专业的景点搜索助手。

你的任务是:
1. 根据用户指定的城市和偏好，搜索相关的景点信息
2. 返回景点的名称、地址、坐标等详细信息
3. 确保景点信息准确、丰富

当前任务:
- 城市: {city}
- 旅行偏好: {preferences}
- 额外要求: {free_text_input}

请根据以上信息，思考应该搜索哪些类型的景点，并说明理由。
"""


async def poi_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    POI 搜索节点

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    agent_state = AgentState(**state)

    # 记录步骤开始
    step = AgentStep(
        node=NodeType.POI_SEARCH.value,
        status="running",
        input={
            "city": agent_state.city,
            "preferences": agent_state.preferences
        }
    )

    try:
        # 1. 使用 LLM 分析用户偏好，确定搜索关键词
        llm = get_llm(agent_state.llm_provider)

        prompt = ChatPromptTemplate.from_template(POI_AGENT_PROMPT)
        chain = prompt | llm

        response = await chain.ainvoke({
            "city": agent_state.city,
            "preferences": ", ".join(agent_state.preferences) if agent_state.preferences else "景点",
            "free_text_input": agent_state.free_text_input or "无"
        })

        # 2. 根据偏好确定搜索关键词
        search_keywords = agent_state.preferences if agent_state.preferences else ["景点"]

        # 如果没有偏好，使用默认关键词
        if not search_keywords:
            search_keywords = ["景点", "旅游"]

        # 3. 调用高德地图 API 搜索 POI
        amap = get_amap_service()
        all_pois = []

        for keyword in search_keywords[:3]:  # 最多搜索3个关键词
            pois = await amap.search_poi(keyword, agent_state.city, citylimit=True)
            all_pois.extend(pois)

        # 去重
        seen = set()
        unique_pois = []
        for poi in all_pois:
            if poi.name not in seen:
                seen.add(poi.name)
                unique_pois.append(poi)

        # 4. 更新状态
        step.status = "completed"
        step.output = {
            "pois_count": len(unique_pois),
            "keywords_used": search_keywords
        }
        step.duration_ms = 0  # TODO: 计算实际耗时

        agent_state.pois = unique_pois[:20]  # 最多保留20个
        agent_state.steps.append(step)
        agent_state.current_node = NodeType.POI_SEARCH.value
        agent_state.updated_at = datetime.now()

        return agent_state.model_dump()

    except Exception as e:
        step.status = "failed"
        step.error = str(e)
        agent_state.errors.append(f"POI搜索失败: {str(e)}")
        agent_state.steps.append(step)
        return agent_state.model_dump()


# 导入 datetime
from datetime import datetime
