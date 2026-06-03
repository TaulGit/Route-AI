"""意图分析节点 — LLM解析用户意图 + 加载用户历史画像"""

from typing import Dict, Any
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate

from ...core.llm import get_llm
from ...services.preference_service import get_preference_service
from ...models.schemas import AgentState, AgentStep, NodeType


INTENT_ANALYSIS_PROMPT = """你是一个智能路线规划系统的意图分析模块。请分析用户的出行需求。

城市: {city}
出行日期: {date}
出发时间: {start_time} - {end_time}
交通方式: {transportation}
显式偏好: {preferences}
额外要求: {free_text}
{user_profile_section}

请分析并返回JSON格式结果（不要markdown代码块）:
{{
  "primary_goal": "用户的主要目标(如: 美食探索/文化游览/购物休闲/综合体验)",
  "must_visit_keywords": ["必须包含的关键词"],
  "avoid_keywords": ["需要避开的关键词"],
  "time_flexibility": "strict/flexible",
  "budget_priority": "high/medium/low",
  "preference_weights": {{"历史文化": 0.5, "美食": 0.8, ...}},
  "mood": "用户的出行心情(悠闲/高效/浪漫/亲子等)",
  "special_requirements": ["特殊要求"]
}}"""


async def intent_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    意图分析节点

    1. LLM解析用户意图和需求
    2. 加载用户历史画像(如有user_id)
    3. 合并显式偏好和历史偏好
    """
    agent_state = AgentState(**state)
    print(f"\n[IntentAnalysis] 开始分析用户意图")

    step = AgentStep(
        node=NodeType.INTENT_ANALYSIS.value,
        status="running",
        input={"city": agent_state.city}
    )

    try:
        # 1. 加载用户画像
        user_id = getattr(agent_state, 'user_id', None)
        user_profile_section = ""
        user_profile = None

        if user_id:
            pref_service = get_preference_service()
            user_profile = await pref_service.get_user_profile(user_id)
            if user_profile:
                # 合并偏好
                merged = await pref_service.get_personalized_preferences(
                    user_id, agent_state.preferences
                )
                agent_state.preferences = merged

                user_profile_section = f"""
用户历史偏好:
- 偏好类别权重: {user_profile.preferred_categories}
- 预算偏好: {user_profile.budget_preference}
- 交通偏好: {user_profile.transport_preference}
- 访问历史: {', '.join(user_profile.visit_history[-10:]) if user_profile.visit_history else '无'}
"""
                print(f"[IntentAnalysis] 已加载用户 {user_id} 的画像")

        # 2. LLM分析意图
        llm = get_llm(agent_state.llm_provider, temperature=0.3, max_tokens=600)
        prompt = ChatPromptTemplate.from_template(INTENT_ANALYSIS_PROMPT)
        chain = prompt | llm

        start_time = getattr(agent_state, 'start_time', '09:00') or '09:00'
        end_time = getattr(agent_state, 'end_time', '18:00') or '18:00'
        date = getattr(agent_state, 'date', agent_state.start_date or '')

        response = await chain.ainvoke({
            "city": agent_state.city,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "transportation": getattr(agent_state, 'transportation', '公共交通') or '公共交通',
            "preferences": ", ".join(agent_state.preferences) if agent_state.preferences else "无特殊偏好",
            "free_text": agent_state.free_text_input or "无",
            "user_profile_section": user_profile_section
        })

        content = response.content if hasattr(response, 'content') else str(response)

        # 3. 解析LLM返回的意图
        import json, re
        intent = {}
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                intent = json.loads(match.group())
            except json.JSONDecodeError:
                # 解析失败时使用默认值
                intent = {
                    "primary_goal": "综合体验",
                    "preference_weights": {}
                }

        print(f"[IntentAnalysis] 意图: {intent.get('primary_goal', '未知')}")

        # 4. 更新状态
        step.status = "completed"
        step.output = intent

        agent_state.current_node = NodeType.INTENT_ANALYSIS.value
        agent_state.steps.append(step)
        agent_state.updated_at = datetime.now()

        state_update = agent_state.model_dump()
        state_update["intent"] = intent
        if user_profile:
            state_update["user_profile"] = user_profile.model_dump()

        return state_update

    except Exception as e:
        step.status = "failed"
        step.error = str(e)
        agent_state.errors.append(f"意图分析失败: {str(e)}")
        agent_state.steps.append(step)
        agent_state.current_node = NodeType.INTENT_ANALYSIS.value
        return agent_state.model_dump()
