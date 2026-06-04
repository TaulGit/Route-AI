"""路线优化节点 — 距离矩阵 + TSP排序 + LLM偏好重排"""

from typing import Dict, Any, List
import asyncio

from ...models.schemas import AgentState, POI, RouteSegment, OptimizationMetrics, Location
from ...services.route_service import get_route_service
from ...services.amap_service import get_amap_service
from ...core.llm import get_llm


async def route_optimizer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    路线优化节点

    1. 从POI列表中筛选和排序
    2. 构建距离矩阵
    3. TSP贪心排序
    4. LLM偏好重排
    5. 生成路线段
    """
    agent_state = AgentState(**state)
    print(f"\n[RouteOptimizer] 开始路线优化, 共 {len(agent_state.pois)} 个POI")

    # 1. 获取已富化的POI列表
    pois = agent_state.pois
    if not pois:
        print("[RouteOptimizer] 无POI数据，跳过优化")
        agent_state.steps.append({
            "node": "route_optimizer",
            "status": "failed",
            "message": "没有可用的POI数据"
        })
        agent_state.current_node = "route_optimizer"
        return agent_state.model_dump()

    # 2. 筛选有坐标且评分合格的POI
    valid_pois = [p for p in pois if p.location and p.location.longitude != 0 and p.location.latitude != 0]
    print(f"[RouteOptimizer] 有效POI(有坐标): {len(valid_pois)}")

    if len(valid_pois) < 2:
        print("[RouteOptimizer] 有效POI不足2个，无法优化路线")
        agent_state.current_node = "route_optimizer"
        return agent_state.model_dump()

    # 3. POI评分和选择
    transport_mode = agent_state.transportation or "公共交通"
    # 根据偏好关键词调整评分权重
    scored_pois = _score_pois(valid_pois, agent_state.preferences, agent_state.free_text_input)

    # 选择 top N POI（默认5个）
    target_count = getattr(agent_state, 'poi_count', 5) if hasattr(agent_state, 'poi_count') else 5
    selected_pois = scored_pois[:target_count]
    print(f"[RouteOptimizer] 选择了 {len(selected_pois)} 个POI")

    # 4. 构建距离矩阵
    route_service = get_route_service()
    amap = get_amap_service()

    # 确定起点
    start_location = None
    start_address = getattr(agent_state, 'start_address', None)
    if not start_location and start_address:
        start_location = await amap.geocode(start_address, agent_state.city)

    # 如果没有明确的出发地，用第一个POI作为默认起点
    city_center = await amap.geocode(agent_state.city)
    if not start_location:
        start_location = city_center

    # 把起点加入POI列表用于矩阵计算
    all_points = list(selected_pois)
    start_poi = POI(
        id="start",
        name="出发地点",
        address=start_address or agent_state.city,
        location=start_location,
        category="起点"
    )
    all_points.insert(0, start_poi)

    matrix = await route_service.build_distance_matrix(all_points, agent_state.city, transport_mode)

    # 5. TSP贪心排序（从起点出发）
    ordered_indices = route_service.solve_tsp_greedy(all_points, matrix, start_index=0)
    print(f"[RouteOptimizer] 贪心TSP排序: {ordered_indices}")

    # 去掉起点(索引0)，但保留第一个POI作为起点后的第一个目的地
    poo_order = [idx - 1 for idx in ordered_indices if idx > 0]  # 索引映射回selected_pois

    # 6. LLM偏好重排（如果有明确偏好）
    free_text = agent_state.free_text_input or ""
    preferences = agent_state.preferences or []
    if free_text or len(preferences) > 1:
        try:
            poo_order = await _llm_rerank(
                selected_pois, poo_order,
                agent_state.preferences,
                free_text,
                matrix,
                transport_mode,
                agent_state.llm_provider or "deepseek"
            )
        except Exception as e:
            print(f"[RouteOptimizer] LLM重排失败，使用贪心结果: {e}")

    # 重新排序POI
    ordered_pois_list = [selected_pois[i] for i in poo_order if i < len(selected_pois)]

    # 7. 构建路线段
    segments = route_service.build_route_segments(
        [i + 1 for i in poo_order],  # all_points索引
        all_points,
        matrix,
        start_location=start_location
    )

    # 为每个段补充起点/终点POI名称
    for seg in segments:
        if not seg.from_poi or seg.from_poi == "":
            # 从seg.from_location/to_location反查POI名称
            pass

    # 如果没有足够的段（只有直接估算的），构建基本段
    if not segments:
        for k in range(len(ordered_pois_list)):
            if k == 0 and start_location:
                seg = route_service._estimate_by_straight_line(
                    start_location, ordered_pois_list[0].location, transport_mode
                )
                if seg:
                    seg.from_poi = "出发地点"
                    seg.to_poi = ordered_pois_list[0].name
                    segments.append(seg)
            if k < len(ordered_pois_list) - 1:
                seg = route_service._estimate_by_straight_line(
                    ordered_pois_list[k].location,
                    ordered_pois_list[k+1].location,
                    transport_mode
                )
                if seg:
                    seg.from_poi = ordered_pois_list[k].name
                    seg.to_poi = ordered_pois_list[k+1].name
                    segments.append(seg)

    # 8. 计算总距离和总时间
    total_distance_km = sum(s.distance_meters for s in segments) / 1000
    total_duration = sum(s.duration_minutes for s in segments)
    total_cost = sum(s.cost_estimate for s in segments)

    # 9. 计算时间预算
    start_time = getattr(agent_state, 'start_time', None)
    end_time = getattr(agent_state, 'end_time', None)
    time_budget = 480  # 默认8小时
    if start_time and end_time:
        try:
            sh, sm = map(int, start_time.split(":"))
            eh, em = map(int, end_time.split(":"))
            time_budget = (eh * 60 + em) - (sh * 60 + sm)
        except (ValueError, TypeError):
            pass

    # 加上POI游览时间
    visit_time = sum(p.visit_duration or 120 for p in ordered_pois_list)
    total_time_with_visit = total_duration + visit_time

    # 10. 计算优化指标
    metrics = route_service.calculate_optimization_metrics(
        segments=segments,
        total_duration_minutes=total_time_with_visit,
        time_budget_minutes=time_budget,
        budget_total=total_cost,
        budget_range=agent_state.budget if hasattr(agent_state, 'budget') else None,
        preference_match_score=_calculate_preference_match(ordered_pois_list, agent_state.preferences)
    )

    # 更新状态
    agent_state.current_node = "route_optimizer"
    agent_state.steps.append({
        "node": "route_optimizer",
        "status": "completed",
        "message": f"路线优化完成: {len(ordered_pois_list)}个POI, 总距离{total_distance_km:.1f}km, 预估耗时{total_time_with_visit}分钟"
    })

    # 将路线数据存入state（后续节点使用）
    # 先存到 agent_state 的字段里，确保 model_dump 能正确序列化
    agent_state.ordered_pois = [p.model_dump() if hasattr(p, 'model_dump') else p for p in ordered_pois_list]
    agent_state.route_segments = [s.model_dump() if hasattr(s, 'model_dump') else s for s in segments]
    agent_state.optimization_metrics = metrics
    agent_state.total_distance_km = total_distance_km
    agent_state.total_duration_minutes = total_time_with_visit
    agent_state.total_cost = total_cost
    if start_location:
        agent_state.start_location = start_location.model_dump() if hasattr(start_location, 'model_dump') else start_location

    state_update = agent_state.model_dump()
    return state_update


def _score_pois(pois: List[POI], preferences: List[str], free_text: str = "") -> List[POI]:
    """根据偏好对POI进行评分排序"""
    pref_keywords = " ".join(preferences).lower() if preferences else ""
    free_lower = free_text.lower() if free_text else ""
    all_pref = pref_keywords + " " + free_lower

    def score(poi: POI) -> float:
        s = 0.0
        # 评分权重
        if poi.rating:
            s += poi.rating * 10
        # 热度权重
        if getattr(poi, 'popularity_score', None):
            s += poi.popularity_score * 0.5
        # 偏好匹配
        name_cat = (poi.name + " " + (poi.category or "")).lower()
        for p in (preferences or []):
            if p in name_cat:
                s += 20
        # 免费文本匹配
        if free_lower and poi.name.lower() in free_lower:
            s += 15
        # 有评价的加分
        if poi.rating and poi.rating > 3.5:
            s += 10
        return s

    scored = sorted(pois, key=score, reverse=True)
    print(f"[RouteOptimizer] POI评分排序: {[(p.name, round(score(p), 1)) for p in scored[:10]]}")
    return scored


async def _llm_rerank(
    pois: List[POI],
    current_order: List[int],
    preferences: List[str],
    free_text: str,
    matrix: Dict,
    transport_mode: str,
    llm_provider: str
) -> List[int]:
    """使用LLM进行偏好感知的路线重排"""
    # 构建POI信息文本
    poi_info = ""
    for idx in current_order:
        if idx < len(pois):
            p = pois[idx]
            rating_str = f"评分{p.rating}" if p.rating else "暂无评分"
            poi_info += f"- [{idx}] {p.name} ({p.category or '未分类'}) - {rating_str} - {p.address}\n"

    prompt = f"""你是一个路线规划专家。以下是按距离贪心排序后的POI访问顺序，请根据用户偏好重新排序。

用户偏好: {', '.join(preferences) if preferences else '无特殊偏好'}
额外要求: {free_text if free_text else '无'}
交通方式: {transport_mode}

当前排序（按距离贪心）:
{poi_info}

请根据以下原则重新排序:
1. 用户偏好高的POI优先
2. 考虑用餐时间（午餐12:00左右应安排在餐饮POI附近）
3. 评分高、口碑好的POI适当提前
4. 同类POI不要连续安排太多
5. 地理上仍需合理（不能跳来跳去）

请返回新的访问顺序（仅返回索引列表，如 [2, 0, 1, 3]），不要其他内容。"""

    llm = get_llm(llm_provider, temperature=0.3, max_tokens=200)
    response = await llm.ainvoke(prompt)

    # 解析LLM返回的索引列表
    import re
    content = response.content if hasattr(response, 'content') else str(response)
    match = re.search(r'\[[\d,\s]+\]', content)
    if match:
        try:
            new_order = eval(match.group())
            # 验证所有索引都在有效范围内
            new_order = [i for i in new_order if 0 <= i < len(pois)]
            if len(new_order) >= 2:
                print(f"[RouteOptimizer] LLM重排结果: {new_order}")
                return new_order
        except:
            pass

    return current_order


def _calculate_preference_match(ordered_pois: List[POI], preferences: List[str]) -> float:
    """计算偏好匹配度"""
    if not preferences:
        return 70.0

    match_count = 0
    for poi in ordered_pois:
        name_cat = (poi.name + " " + (poi.category or "")).lower()
        for pref in preferences:
            if pref.lower() in name_cat:
                match_count += 1
                break

    if not ordered_pois:
        return 50.0

    ratio = match_count / len(ordered_pois)
    return min(100, ratio * 100 + 30)
