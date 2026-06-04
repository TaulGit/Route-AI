"""行程规划 Agent 节点 - 主 Agent (支持旅行规划和本地路线规划)"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from langchain_core.prompts import ChatPromptTemplate

from ...core.llm import get_llm
from ...models.schemas import (
    AgentState, AgentStep, NodeType, TripStatus,
    TripPlan, DayPlan, Attraction, Meal, Location, Hotel, Budget,
    RoutePlan, RouteSegment, OptimizationMetrics, POI
)


PLANNER_AGENT_PROMPT = """你是一个专业的旅行规划师。

根据以下信息，生成一份详细的旅行计划。

## 基本信息
- 城市: {city}
- 日期范围: {start_date} 至 {end_date}
- 旅行天数: {travel_days} 天
- 交通方式: {transportation}
- 住宿偏好: {accommodation}
- 用户偏好: {preferences}

## 可用景点 (POI)
{pois_info}

## 天气预报
{weather_info}

## 可用酒店
{hotels_info}

## 任务要求
1. 从可用景点中选择合适的景点，每天安排 2-3 个
2. 使用景点列表中提供的真实坐标
3. 为每天安排早餐、午餐、晚餐
4. 推荐合适的酒店
5. 生成合理的预算估算

请严格按照以下 JSON 格式输出，不要添加任何其他内容:

{{
  "city": "城市名称",
  "start_date": "开始日期",
  "end_date": "结束日期",
  "days": [
    {{
      "date": "日期",
      "day_index": 0,
      "description": "当日行程描述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {{
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {{"longitude": 0, "latitude": 0}},
        "price_range": "价格范围",
        "rating": "评分",
        "type": "酒店类型",
        "estimated_cost": 300
      }},
      "attractions": [
        {{
          "name": "景点名称",
          "address": "景点地址",
          "location": {{"longitude": 0, "latitude": 0}},
          "visit_duration": 120,
          "description": "景点描述",
          "category": "景点类别",
          "ticket_price": 60
        }}
      ],
      "meals": [
        {{"type": "breakfast", "name": "早餐名称", "description": "描述", "estimated_cost": 30}},
        {{"type": "lunch", "name": "午餐名称", "description": "描述", "estimated_cost": 50}},
        {{"type": "dinner", "name": "晚餐名称", "description": "描述", "estimated_cost": 80}}
      ]
    }}
  ],
  "weather_info": [],
  "overall_suggestions": "总体建议",
  "budget": {{
    "total_attractions": 0,
    "total_hotels": 0,
    "total_meals": 0,
    "total_transportation": 0,
    "total": 0
  }}
}}"""

LOCAL_ROUTE_PROMPT = """你是一个专业的本地路线规划师。根据路线优化结果，为用户生成详细的本地一日游方案。

## 基本信息
- 城市: {city}
- 日期: {date}
- 时间: {start_time} - {end_time}
- 交通方式: {transportation}
- 用户偏好: {preferences}
- 额外要求: {free_text}

## 优化路线 (已按最优顺序排列)
{route_info}

## POI评价摘要
{review_summary}

## 优化指标
- 时间效率: {time_efficiency}分
- 费用效率: {cost_efficiency}分
- 偏好匹配: {preference_match}分
- 路线合理性: {route_coherence}分

## 任务要求
1. 按照优化路线顺序描述行程
2. 在路线段之间合理穿插餐饮推荐（早餐/午餐/下午茶/晚餐）
3. 估算各段时间（含游览+路程）
4. 结合评价数据给出每个POI的Tips
5. 如果某些路段排队时间长，给出避开高峰的建议
6. 输出trade_off_explanations（说明路线取舍的原因）

请严格按照以下 JSON 格式输出:
{{
  "suggestions": "路线总体建议(100字内)",
  "meals": [
    {{"type": "breakfast", "name": "早餐推荐", "description": "推荐理由", "estimated_cost": 30}},
    {{"type": "lunch", "name": "午餐推荐", "description": "推荐理由", "estimated_cost": 60}},
    {{"type": "dinner", "name": "晚餐推荐", "description": "推荐理由", "estimated_cost": 80}}
  ],
  "trade_off_explanations": [
    "路线取舍说明1",
    "路线取舍说明2"
  ]
}}"""


async def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    行程规划节点 - 主 Agent

    自动检测是旅行规划（多日）还是本地路线规划（单日+路线数据）
    """
    agent_state = AgentState(**state)

    # 检测是否为本地路线规划模式（有路线数据）
    has_route_data = bool(
        state.get("route_segments") or state.get("ordered_pois")
    )

    step = AgentStep(
        node=NodeType.PLANNER.value if not has_route_data else NodeType.ITINERARY_GENERATOR.value,
        status="running",
        input={
            "pois_count": len(agent_state.pois),
            "has_route_data": has_route_data
        }
    )

    try:
        if has_route_data:
            # 本地路线规划模式
            route_plan = await _generate_local_route(state, agent_state)
            step.status = "completed"
            step.output = {"route_plan_generated": True}
            agent_state.current_node = NodeType.ITINERARY_GENERATOR.value
        else:
            # 传统旅行规划模式
            pois_info = _format_pois(agent_state.pois)
            weather_info = _format_weather(agent_state.weather)
            hotels_info = _format_hotels(agent_state.hotels)

            llm = get_llm(agent_state.llm_provider, temperature=0.7)
            prompt = ChatPromptTemplate.from_template(PLANNER_AGENT_PROMPT)
            chain = prompt | llm

            response = await chain.ainvoke({
                "city": agent_state.city,
                "start_date": agent_state.start_date,
                "end_date": agent_state.end_date,
                "travel_days": agent_state.travel_days,
                "transportation": agent_state.transportation,
                "accommodation": agent_state.accommodation,
                "preferences": ", ".join(agent_state.preferences) if agent_state.preferences else "无特殊偏好",
                "pois_info": pois_info,
                "weather_info": weather_info,
                "hotels_info": hotels_info
            })

            trip_plan = _parse_trip_plan(response.content, agent_state)
            agent_state.itinerary = trip_plan
            step.status = "completed"
            step.output = {"plan_generated": True}
            agent_state.current_node = NodeType.PLANNER.value

        step.duration_ms = 0
        agent_state.steps.append(step)
        agent_state.status = TripStatus.NEED_CONFIRM
        agent_state.need_human_review = True
        agent_state.updated_at = datetime.now()

        return agent_state.model_dump()

    except Exception as e:
        step.status = "failed"
        step.error = str(e)
        agent_state.errors.append(f"行程规划失败: {str(e)}")
        agent_state.steps.append(step)

        # 生成 fallback
        if has_route_data:
            agent_state.itinerary = _create_fallback_route(state, agent_state)
        else:
            agent_state.itinerary = _create_fallback_plan(agent_state)

        if agent_state.itinerary:
            agent_state.status = TripStatus.NEED_CONFIRM
            agent_state.need_human_review = True

        return agent_state.model_dump()


async def _generate_local_route(state: Dict[str, Any], agent_state: AgentState) -> Optional[RoutePlan]:
    """生成本地路线方案"""
    # 格式化路线信息
    route_info_lines = []
    ordered_pois_raw = state.get("ordered_pois", [])
    segments_raw = state.get("route_segments", [])

    for i, poi_dict in enumerate(ordered_pois_raw):
        name = poi_dict.get("name", f"POI{i+1}")
        rating = poi_dict.get("rating", "")
        pop = poi_dict.get("popularity_score", "")
        queue = poi_dict.get("queue_time_min", "")
        route_info_lines.append(f"{i+1}. {name} (评分:{rating}, 热度:{pop}, 排队:{queue}min)")

    if segments_raw:
        route_info_lines.append("\n路线段:")
        total_dist = state.get("total_distance_km", 0)
        total_dur = state.get("total_duration_minutes", 0)
        for j, seg in enumerate(segments_raw):
            route_info_lines.append(
                f"  {seg.get('from_poi','')} -> {seg.get('to_poi','')}: "
                f"{seg.get('distance_meters',0)}m, {seg.get('duration_minutes',0)}min, "
                f"{seg.get('transport_mode','walking')}"
            )
        route_info_lines.append(f"总距离: {total_dist:.1f}km, 总耗时: {total_dur}min")

    route_info = "\n".join(route_info_lines) if route_info_lines else "暂无路线数据"

    # 格式化评价摘要
    review_lines = []
    for poi_dict in ordered_pois_raw:
        name = poi_dict.get("name", "")
        rating = poi_dict.get("rating", "")
        pop = poi_dict.get("popularity_score", "")
        queue = poi_dict.get("queue_time_min", "")
        review_lines.append(f"- {name}: 评分{rating}, 热度{pop}, 预估排队{queue}min")
    review_summary = "\n".join(review_lines) if review_lines else "暂无评价数据"

    # 优化指标
    metrics = state.get("optimization_metrics", {})
    time_eff = metrics.get("time_efficiency", 80)
    cost_eff = metrics.get("cost_efficiency", 80)
    pref_match = metrics.get("preference_match", 70)
    route_coh = metrics.get("route_coherence", 70)

    # 调用LLM生成方案
    llm = get_llm(agent_state.llm_provider, temperature=0.7, max_tokens=800)
    prompt = ChatPromptTemplate.from_template(LOCAL_ROUTE_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "city": agent_state.city,
        "date": state.get("date", agent_state.start_date or datetime.now().strftime("%Y-%m-%d")),
        "start_time": state.get("start_time", "09:00"),
        "end_time": state.get("end_time", "18:00"),
        "transportation": agent_state.transportation or "公共交通",
        "preferences": ", ".join(agent_state.preferences) if agent_state.preferences else "无特殊偏好",
        "free_text": agent_state.free_text_input or "无",
        "route_info": route_info,
        "review_summary": review_summary,
        "time_efficiency": str(time_eff),
        "cost_efficiency": str(cost_eff),
        "preference_match": str(pref_match),
        "route_coherence": str(route_coh)
    })

    content = response.content if hasattr(response, 'content') else str(response)

    # 解析LLM输出
    suggestions = ""
    meals = []
    trade_offs = []

    try:
        import re
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            data = json.loads(match.group())
            suggestions = data.get("suggestions", "")
            for m in data.get("meals", []):
                meals.append(Meal(
                    type=m.get("type", "lunch"),
                    name=m.get("name", ""),
                    description=m.get("description", ""),
                    estimated_cost=m.get("estimated_cost", 0)
                ))
            trade_offs = data.get("trade_off_explanations", [])
    except (json.JSONDecodeError, Exception) as e:
        print(f"[Planner] 解析本地路线LLM响应失败: {e}")
        suggestions = f"为您规划的{agent_state.city}一日游路线，共{len(ordered_pois_raw)}个目的地。"
        meals = [
            Meal(type="breakfast", name="早餐", description="当地特色早餐", estimated_cost=30),
            Meal(type="lunch", name="午餐", description="当地特色午餐", estimated_cost=60),
            Meal(type="dinner", name="晚餐", description="当地特色晚餐", estimated_cost=80)
        ]

    # 构建Ordered POI的Attraction对象
    ordered_attractions = []
    for poi_dict in ordered_pois_raw:
        try:
            if isinstance(poi_dict, dict):
                loc = poi_dict.get("location") or {}
                name = poi_dict.get("name") or ""
                address = poi_dict.get("address") or ""
                visit_duration = poi_dict.get("visit_duration") or 120
                description = poi_dict.get("description") or ""
                category = poi_dict.get("category") or ""
                ticket_price = poi_dict.get("ticket_price") or 0
            else:
                loc = getattr(poi_dict, 'location', None)
                name = getattr(poi_dict, 'name', '') or ''
                address = getattr(poi_dict, 'address', '') or ''
                visit_duration = getattr(poi_dict, 'visit_duration', 120) or 120
                description = getattr(poi_dict, 'description', '') or ''
                category = getattr(poi_dict, 'category', '') or ''
                ticket_price = getattr(poi_dict, 'ticket_price', 0) or 0
            ordered_attractions.append(Attraction(
                name=name,
                address=address,
                location=Location(
                    longitude=loc.get("longitude", 0) if isinstance(loc, dict) else (getattr(loc, 'longitude', 0) if loc else 0),
                    latitude=loc.get("latitude", 0) if isinstance(loc, dict) else (getattr(loc, 'latitude', 0) if loc else 0)
                ),
                visit_duration=visit_duration,
                description=description,
                category=category,
                ticket_price=ticket_price
            ))
        except Exception as e:
            print(f"[Planner] POI[{i}] 构建失败: {e}")

    # 构建RouteSegments
    route_segments = []
    for seg_dict in segments_raw:
        try:
            fl = seg_dict.get("from_location") or {}
            tl = seg_dict.get("to_location") or {}
            route_segments.append(RouteSegment(
                from_poi=seg_dict.get("from_poi") or "",
                to_poi=seg_dict.get("to_poi") or "",
                from_location=Location(
                    longitude=fl.get("longitude", 0) if isinstance(fl, dict) else 0,
                    latitude=fl.get("latitude", 0) if isinstance(fl, dict) else 0
                ),
                to_location=Location(
                    longitude=tl.get("longitude", 0) if isinstance(tl, dict) else 0,
                    latitude=tl.get("latitude", 0) if isinstance(tl, dict) else 0
                ),
                distance_meters=seg_dict.get("distance_meters", 0),
                duration_minutes=seg_dict.get("duration_minutes", 0),
                polyline=seg_dict.get("polyline", ""),
                transport_mode=seg_dict.get("transport_mode", "walking"),
                cost_estimate=seg_dict.get("cost_estimate", 0)
            ))
        except Exception:
            pass

    # 天气
    weather = None
    if state.get("weather") and len(state["weather"]) > 0:
        from ...models.schemas import Weather
        w = state["weather"][0]
        if isinstance(w, dict):
            weather = Weather(**w)

    # 构建RoutePlan
    route_plan = RoutePlan(
        city=agent_state.city,
        date=state.get("date", agent_state.start_date or datetime.now().strftime("%Y-%m-%d")),
        start_location=Location(**state["start_location"]) if state.get("start_location") else None,
        start_time=state.get("start_time"),
        ordered_pois=ordered_attractions,
        route_segments=route_segments,
        total_distance_km=state.get("total_distance_km", 0),
        total_duration_minutes=state.get("total_duration_minutes", 0),
        total_cost=state.get("total_cost", 0),
        optimization_metrics=OptimizationMetrics(
            time_efficiency=metrics.get("time_efficiency", 80),
            cost_efficiency=metrics.get("cost_efficiency", 80),
            preference_match=metrics.get("preference_match", 70),
            route_coherence=metrics.get("route_coherence", 70),
            overall_score=metrics.get("overall_score", 75)
        ) if metrics else None,
        meals=meals,
        weather=weather,
        suggestions=suggestions,
        trade_off_explanations=trade_offs
    )

    # 存到itinerary（作为dict以便和旧代码兼容）
    agent_state.itinerary = route_plan.model_dump()
    return route_plan


def _format_pois(pois: list) -> str:
    """格式化 POI 信息"""
    if not pois:
        return "暂无景点信息"

    lines = []
    for i, poi in enumerate(pois[:15], 1):
        poi_dict = poi if isinstance(poi, dict) else poi.model_dump() if hasattr(poi, 'model_dump') else {}
        name = poi_dict.get("name", poi.name if hasattr(poi, 'name') else str(poi))
        address = poi_dict.get("address", poi.address if hasattr(poi, 'address') else "")
        loc = poi_dict.get("location", {})
        rating = poi_dict.get("rating", None)
        pop = poi_dict.get("popularity_score", "")
        queue = poi_dict.get("queue_time_min", "")

        lines.append(f"{i}. {name}")
        lines.append(f"   地址: {address}")
        if isinstance(loc, dict):
            lines.append(f"   坐标: ({loc.get('longitude', 0)}, {loc.get('latitude', 0)})")
        elif hasattr(loc, 'longitude'):
            lines.append(f"   坐标: ({loc.longitude}, {loc.latitude})")
        if rating:
            lines.append(f"   评分: {rating}")
        if pop:
            lines.append(f"   热度: {pop}  排队: {queue}min")
        lines.append("")

    return "\n".join(lines)


def _format_weather(weather: list) -> str:
    """格式化天气信息"""
    if not weather:
        return "暂无天气信息"

    lines = []
    for w in weather:
        if isinstance(w, dict):
            lines.append(f"{w.get('date', '')}: {w.get('day_weather', '')} {w.get('day_temp', '')}°C / {w.get('night_weather', '')} {w.get('night_temp', '')}°C")
        elif hasattr(w, 'date'):
            lines.append(f"{w.date}: {w.day_weather} {w.day_temp}°C / {w.night_weather} {w.night_temp}°C")

    return "\n".join(lines)


def _format_hotels(hotels: list) -> str:
    """格式化酒店信息"""
    if not hotels:
        return "暂无酒店信息"

    lines = []
    for i, h in enumerate(hotels[:5], 1):
        if isinstance(h, dict):
            lines.append(f"{i}. {h.get('name', '')} - {h.get('address', '')}")
            if h.get('rating'):
                lines.append(f"   评分: {h.get('rating')}")
        elif hasattr(h, 'name'):
            lines.append(f"{i}. {h.name} - {h.address}")
            if h.rating:
                lines.append(f"   评分: {h.rating}")

    return "\n".join(lines)


def _parse_trip_plan(response: str, state: AgentState) -> TripPlan:
    """解析LLM响应为TripPlan"""
    json_str = response

    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        if end > start:
            json_str = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end > start:
            json_str = response[start:end].strip()

    if "{" in json_str:
        start = json_str.find("{")
        brace_count = 0
        end = start
        for i, char in enumerate(json_str[start:], start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        json_str = json_str[start:end]

    data = json.loads(json_str)
    return TripPlan(**data)


def _create_fallback_plan(state: AgentState) -> TripPlan:
    """创建 fallback 旅行计划"""
    start_date = datetime.strptime(state.start_date, "%Y-%m-%d")

    attractions = []
    for poi in state.pois[:3]:
        poi_dict = poi if isinstance(poi, dict) else poi.model_dump() if hasattr(poi, 'model_dump') else {}
        loc_data = poi_dict.get("location", {})
        attractions.append(Attraction(
            name=poi_dict.get("name", f"{state.city}景点"),
            address=poi_dict.get("address", state.city),
            location=Location(
                longitude=loc_data.get("longitude", 116.4) if isinstance(loc_data, dict) else 116.4,
                latitude=loc_data.get("latitude", 39.9) if isinstance(loc_data, dict) else 39.9
            ),
            visit_duration=120,
            description=f"{state.city}推荐景点",
            category=poi_dict.get("category", "景点")
        ))

    if not attractions:
        attractions = [Attraction(
            name=f"{state.city}市中心景点",
            address=f"{state.city}市中心",
            location=Location(longitude=116.4, latitude=39.9),
            visit_duration=120,
            description="推荐景点"
        )]

    days = []
    for i in range(state.travel_days):
        current_date = start_date + timedelta(days=i)
        days.append(DayPlan(
            date=current_date.strftime("%Y-%m-%d"),
            day_index=i,
            description=f"第{i+1}天 - {state.city}游览",
            transportation=state.transportation,
            accommodation=state.accommodation,
            attractions=attractions,
            meals=[
                Meal(type="breakfast", name="早餐", description="当地特色早餐", estimated_cost=30),
                Meal(type="lunch", name="午餐", description="当地特色午餐", estimated_cost=50),
                Meal(type="dinner", name="晚餐", description="当地特色晚餐", estimated_cost=80)
            ]
        ))

    return TripPlan(
        city=state.city,
        start_date=state.start_date,
        end_date=state.end_date,
        days=days,
        weather_info=state.weather,
        overall_suggestions=f"这是{state.city}的{state.travel_days}天旅行计划。"
    )


def _create_fallback_route(state: Dict[str, Any], agent_state: AgentState) -> Optional[RoutePlan]:
    """创建 fallback 路线方案"""
    ordered_raw = state.get("ordered_pois", [])
    if not ordered_raw:
        return None

    attractions = []
    for poi_dict in ordered_raw:
        loc = poi_dict.get("location", {})
        attractions.append(Attraction(
            name=poi_dict.get("name", ""),
            address=poi_dict.get("address", ""),
            location=Location(
                longitude=loc.get("longitude", 0) if isinstance(loc, dict) else 0,
                latitude=loc.get("latitude", 0) if isinstance(loc, dict) else 0
            ),
            visit_duration=poi_dict.get("visit_duration", 120),
            description=poi_dict.get("description", ""),
            category=poi_dict.get("category", ""),
            ticket_price=poi_dict.get("ticket_price", 0)
        ))

    return RoutePlan(
        city=agent_state.city,
        date=state.get("date", agent_state.start_date or ""),
        ordered_pois=attractions,
        route_segments=[],
        total_distance_km=state.get("total_distance_km", 0),
        total_duration_minutes=state.get("total_duration_minutes", 0),
        total_cost=state.get("total_cost", 0),
        suggestions=f"为您规划的{agent_state.city}一日游路线。"
    )
