"""LangGraph 主图定义 - 本地智能路线规划 Agent 协作流程"""

from typing import TypedDict, Optional, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.schemas import TripStatus

# 导入所有节点
from .nodes.poi_agent import poi_search_node
from .nodes.weather_agent import weather_node
from .nodes.hotel_agent import hotel_node
from .nodes.planner_agent import planner_node
from .nodes.human_review import human_review_node
from .nodes.intent_analysis import intent_analysis_node
from .nodes.review_enrich import review_enrich_node
from .nodes.route_optimizer import route_optimizer_node


# ============================================
# GraphState — 本地路线规划状态
# ============================================

class GraphState(TypedDict, total=False):
    """本地路线规划图状态"""
    # 基本输入
    session_id: str
    user_id: Optional[str]
    city: str
    start_date: str
    end_date: str
    date: str  # 单日路线日期
    travel_days: int
    transportation: str
    accommodation: str
    preferences: list
    free_text_input: str
    budget: Optional[list]
    llm_provider: str
    poi_count: int
    start_time: str
    end_time: str
    start_address: Optional[str]
    start_location: Optional[dict]

    # 意图分析输出
    intent: dict
    user_profile: Optional[dict]

    # 中间输出
    pois: list
    weather: list
    hotels: list
    route_segments: list
    ordered_pois: list
    optimization_metrics: dict
    total_distance_km: float
    total_duration_minutes: int
    total_cost: float
    time_budget_minutes: int

    # 最终输出
    itinerary: dict

    # 控制字段
    current_node: str
    status: str
    steps: list
    errors: list
    need_human_review: bool
    human_feedback: str


# ============================================
# 条件路由函数
# ============================================

def should_get_weather(state: GraphState) -> Literal["weather", "review_enrich"]:
    """判断是否需要获取天气数据"""
    preferences = state.get("preferences", [])
    # 偏好包含户外活动时才获取天气
    outdoor_keywords = ["自然风光", "户外", "爬山", "公园", "徒步", "景区", "拍照", "打卡"]
    for pref in preferences:
        for kw in outdoor_keywords:
            if kw in pref:
                return "weather"
    # 默认跳过天气
    return "review_enrich"


def after_planner(state: GraphState) -> Literal["budget_validator", "human_review", "end"]:
    """规划完成后的条件路由"""
    status = state.get("status", "")

    if status == TripStatus.FAILED.value:
        return "end"

    if state.get("need_human_review"):
        return "human_review"

    # 有路线数据则进入预算校验
    if state.get("itinerary") or state.get("route_segments"):
        return "budget_validator"

    return "human_review"


def after_budget(state: GraphState) -> Literal["human_review", "end"]:
    """预算校验后的路由"""
    status = state.get("status", "")
    if status == TripStatus.FAILED.value:
        return "end"
    return "human_review"


# ============================================
# 旧版旅行规划 Graph (保留兼容)
# ============================================

def create_trip_planner_graph():
    """
    创建旅行规划图（旧版，保留兼容）

    图结构:
    START -> poi_search -> weather -> hotel -> planner -> human_review -> END
    """
    workflow = StateGraph(GraphState)

    workflow.add_node("poi_search", poi_search_node)
    workflow.add_node("weather", weather_node)
    workflow.add_node("hotel", hotel_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("human_review", human_review_node)

    workflow.set_entry_point("poi_search")
    workflow.add_edge("poi_search", "weather")
    workflow.add_edge("weather", "hotel")
    workflow.add_edge("hotel", "planner")

    workflow.add_conditional_edges(
        "planner",
        lambda s: "human_review" if s.get("itinerary") else "end",
        {"human_review": "human_review", "end": END}
    )
    workflow.add_edge("human_review", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# ============================================
# 新版本地路线规划 Graph ★核心
# ============================================

def create_local_route_graph():
    """
    创建本地路线规划图

    图结构:
    START -> intent_analysis -> poi_search -> review_enrich -> [weather?]
              -> route_optimizer -> planner -> [budget_validator?] -> human_review -> END
    """
    workflow = StateGraph(GraphState)

    # 注册所有节点
    workflow.add_node("intent_analysis", intent_analysis_node)
    workflow.add_node("poi_search", poi_search_node)
    workflow.add_node("review_enrich", review_enrich_node)
    workflow.add_node("weather", weather_node)
    workflow.add_node("route_optimizer", route_optimizer_node)
    workflow.add_node("planner", planner_node)  # 复用planner作为itinerary_generator
    workflow.add_node("budget_validator", _budget_validator_node)
    workflow.add_node("human_review", human_review_node)

    # 设置入口
    workflow.set_entry_point("intent_analysis")

    # 线性边
    workflow.add_edge("intent_analysis", "poi_search")
    workflow.add_edge("poi_search", "review_enrich")

    # 条件边: review_enrich后决定是否获取天气
    workflow.add_conditional_edges(
        "review_enrich",
        should_get_weather,
        {
            "weather": "weather",
            "review_enrich": "route_optimizer"  # 跳过天气，走这条
        }
    )
    workflow.add_edge("weather", "route_optimizer")

    # 路线优化后进入规划
    workflow.add_edge("route_optimizer", "planner")

    # 规划后的条件路由
    workflow.add_conditional_edges(
        "planner",
        after_planner,
        {
            "budget_validator": "budget_validator",
            "human_review": "human_review",
            "end": END
        }
    )

    # 预算校验后
    workflow.add_conditional_edges(
        "budget_validator",
        after_budget,
        {
            "human_review": "human_review",
            "end": END
        }
    )

    workflow.add_edge("human_review", END)

    # 编译
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


# ============================================
# 预算校验节点
# ============================================

async def _budget_validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """预算校验节点 — 检查行程费用是否在预算范围内"""
    from ..models.schemas import AgentState

    agent_state = AgentState(**state)
    print(f"\n[BudgetValidator] 开始预算校验")

    total_cost = state.get("total_cost", 0)
    budget = state.get("budget")

    budget_valid = True
    message = "预算检查通过"

    if budget and len(budget) == 2:
        budget_min, budget_max = budget[0], budget[1]
        if total_cost > budget_max:
            budget_valid = False
            message = f"总费用{total_cost:.0f}元超出预算上限{budget_max}元，建议调整"
        elif total_cost < budget_min:
            budget_valid = False
            message = f"总费用{total_cost:.0f}元低于预算下限{budget_min}元"
        else:
            message = f"总费用{total_cost:.0f}元，在预算范围{budget_min}-{budget_max}元内"

    print(f"[BudgetValidator] {message}")

    agent_state.current_node = "budget_validator"
    agent_state.steps.append({
        "node": "budget_validator",
        "status": "completed",
        "message": message
    })

    state_update = agent_state.model_dump()
    state_update["budget_valid"] = budget_valid
    return state_update


# ============================================
# 全局实例
# ============================================

_trip_graph = None
_local_route_graph = None


def get_graph():
    """获取旅行规划图实例（旧版兼容）"""
    global _trip_graph
    if _trip_graph is None:
        _trip_graph = create_trip_planner_graph()
    return _trip_graph


def get_local_route_graph():
    """获取本地路线规划图实例"""
    global _local_route_graph
    if _local_route_graph is None:
        _local_route_graph = create_local_route_graph()
    return _local_route_graph
