"""评价增强节点 — 为POI加载/生成UGC评价 + Unsplash实景图片"""

from typing import Dict, Any

from ...models.schemas import AgentState, POI
from ...services.review_service import get_review_service
from ...services.unsplash_service import get_unsplash_service


async def review_enrich_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    评价增强节点

    为每个POI:
    1. 从ChromaDB缓存加载或LLM生成模拟大众点评评价
    2. 计算热度分(popularity_score)
    3. 估算排队时间(queue_time_min)
    4. 搜索Unsplash实景图片
    """
    agent_state = AgentState(**state)
    print(f"\n[ReviewEnrich] 开始评价增强, 共 {len(agent_state.pois)} 个POI")

    if not agent_state.pois:
        print("[ReviewEnrich] 无POI数据，跳过")
        agent_state.current_node = "review_enrich"
        agent_state.steps.append({
            "node": "review_enrich",
            "status": "completed",
            "message": "无POI数据，跳过评价增强"
        })
        return agent_state.model_dump()

    review_service = get_review_service()
    unsplash = get_unsplash_service()
    llm_provider = agent_state.llm_provider or "deepseek"

    # 只对评分最高的前8个POI生成评价（避免慢LLM导致超时）
    pois_to_enrich = agent_state.pois[:8]
    pois_rest = agent_state.pois[8:]
    print(f"[ReviewEnrich] 前8个POI生成评价, 其余{len(pois_rest)}个跳过")

    # 批量增强POI（评价+热度+排队）
    enriched_pois = await review_service.enrich_pois_with_reviews(
        pois=pois_to_enrich,
        city=agent_state.city,
        llm_provider=llm_provider,
        max_concurrent=3
    )

    # 合并未处理的POI
    enriched_pois = enriched_pois + list(pois_rest)

    # Unsplash 图片搜索（只搜前8个有评分的）
    enriched_pois = await unsplash.enrich_pois(enriched_pois[:8], agent_state.city) + enriched_pois[8:]

    # 统计
    with_reviews = sum(1 for p in enriched_pois if (p.popularity_score or 0) > 0)
    high_popularity = sum(1 for p in enriched_pois if (p.popularity_score or 0) > 60)
    has_queue = sum(1 for p in enriched_pois if (p.queue_time_min or 0) > 0)
    with_images = sum(1 for p in enriched_pois if p.image_url)

    agent_state.pois = enriched_pois
    agent_state.current_node = "review_enrich"
    agent_state.steps.append({
        "node": "review_enrich",
        "status": "completed",
        "message": f"评价增强完成: {with_reviews}个有评价, {high_popularity}个高热度, {has_queue}个有排队, {with_images}个有实景图"
    })

    print(f"[ReviewEnrich] 完成: {with_reviews}评价, {high_popularity}高热度, {has_queue}排队, {with_images}图片")

    return agent_state.model_dump()
