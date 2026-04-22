"""旅行规划 API 路由"""

import uuid
import json
import traceback
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

from ...models.schemas import (
    TripRequest, TripPlanResponse, StreamingResponse,
    UserFeedback, TripStatus, TripPlan, DayPlan, Attraction, Meal, Location, Hotel, Budget
)
from ...core.llm import get_llm, invoke_llm_with_logging
from ...services.amap_service import get_amap_service

router = APIRouter(prefix="/trip", tags=["旅行规划"])

# 保存结果的目录
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "saved_results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def _save_trip_result(session_id: str, trip_plan: dict, request: TripRequest):
    """保存行程规划结果到JSON文件"""
    try:
        # 构建保存数据
        save_data = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "request": {
                "city": request.city,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "travel_days": request.travel_days,
                "transportation": request.transportation,
                "accommodation": request.accommodation,
                "preferences": request.preferences,
                "free_text_input": request.free_text_input,
                "budget": request.budget
            },
            "result": trip_plan
        }

        # 生成文件名：城市_日期_session_id.json
        filename = f"{request.city}_{request.start_date}_{session_id[:8]}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        print(f"[Trip Plan] 结果已保存到: {filepath}")
        return filepath
    except Exception as e:
        print(f"[Trip Plan] 保存结果失败: {e}")
        return None


@router.post("/plan")
async def create_trip_plan(request: TripRequest):
    """
    创建旅行计划 - 同步接口
    """
    session_id = request.session_id or str(uuid.uuid4())

    print(f"\n{'='*60}")
    print(f"[Trip Plan] 开始处理请求")
    print(f"[Trip Plan] Session ID: {session_id}")
    print(f"[Trip Plan] 城市: {request.city}")
    print(f"[Trip Plan] 日期: {request.start_date} ~ {request.end_date}")
    print(f"[Trip Plan] 天数: {request.travel_days}")
    print(f"[Trip Plan] LLM Provider: {request.llm_provider}")
    print(f"{'='*60}\n")

    try:
        # 1. 获取地图数据
        print("[Trip Plan] Step 1: 获取地图数据...")
        amap = get_amap_service()

        # 搜索景点
        pois = []
        search_keywords = request.preferences if request.preferences else ["景点"]
        print(f"[Trip Plan] 搜索关键词: {search_keywords}")

        for keyword in search_keywords[:3]:
            try:
                print(f"[Trip Plan] 正在搜索: {keyword}")
                result = await amap.search_poi(keyword, request.city, citylimit=True)
                print(f"[Trip Plan] 找到 {len(result)} 个 {keyword} 相关POI")
                pois.extend(result)
            except Exception as e:
                print(f"[Trip Plan] POI搜索失败: {e}")
                traceback.print_exc()

        # 去重
        seen = set()
        unique_pois = []
        for poi in pois:
            if poi.name not in seen:
                seen.add(poi.name)
                unique_pois.append(poi)

        print(f"[Trip Plan] 去重后共 {len(unique_pois)} 个景点")

        # 搜索酒店
        hotels = []
        try:
            print(f"[Trip Plan] 正在搜索酒店: {request.accommodation}")
            hotels = await amap.search_hotels(request.city, request.accommodation)
            print(f"[Trip Plan] 找到 {len(hotels)} 家酒店")
        except Exception as e:
            print(f"[Trip Plan] 酒店搜索失败: {e}")

        # 获取天气
        weather = []
        try:
            print(f"[Trip Plan] 正在查询天气...")
            weather = await amap.get_weather(request.city)
            print(f"[Trip Plan] 获取到 {len(weather)} 天天气")
        except Exception as e:
            print(f"[Trip Plan] 天气查询失败: {e}")

        # 2. 构建提示词
        print("[Trip Plan] Step 2: 构建 LLM 提示词...")
        pois_info = _format_pois(unique_pois[:15])
        weather_info = _format_weather(weather)
        hotels_info = _format_hotels(hotels[:5])

        # 使用字符串拼接而不是 f-string 避免嵌套过深
        preferences_str = ', '.join(request.preferences) if request.preferences else '无特殊偏好'
        extra_requirements = request.free_text_input or '无'

        prompt = _build_prompt(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            travel_days=request.travel_days,
            transportation=request.transportation,
            accommodation=request.accommodation,
            preferences=preferences_str,
            extra_requirements=extra_requirements,
            pois_info=pois_info,
            weather_info=weather_info,
            hotels_info=hotels_info,
            budget_range=request.budget
        )

        # 3. 调用 LLM
        print("[Trip Plan] Step 3: 调用 LLM...")
        llm_provider = request.llm_provider or "deepseek"
        llm = get_llm(llm_provider)

        # 使用带日志的LLM调用
        llm_response = await invoke_llm_with_logging(llm, prompt, llm_provider)

        # 4. 解析响应
        print("[Trip Plan] Step 4: 解析 LLM 响应...")
        trip_plan = _parse_llm_response(llm_response, request, unique_pois, hotels, weather)
        print(f"[Trip Plan] 解析成功，共 {len(trip_plan.get('days', []))} 天行程")

        # 打印解析后的数据
        print(f"\n{'='*60}")
        print(f"[Trip Plan] 解析后的行程数据:")
        print(f"[Trip Plan] 城市: {trip_plan.get('city')}")
        print(f"[Trip Plan] 日期: {trip_plan.get('start_date')} ~ {trip_plan.get('end_date')}")
        for i, day in enumerate(trip_plan.get('days', [])):
            print(f"[Trip Plan] 第{i+1}天: {day.get('date')}, {len(day.get('attractions', []))} 个景点")
            for j, attr in enumerate(day.get('attractions', [])):
                loc = attr.get('location', {})
                print(f"[Trip Plan]   景点[{j+1}]: {attr.get('name')} @ ({loc.get('longitude')}, {loc.get('latitude')})")
        print(f"{'='*60}\n")

        # 保存结果到文件
        _save_trip_result(session_id, trip_plan, request)

        return {
            "success": True,
            "message": "旅行计划生成成功",
            "data": trip_plan,
            "status": "completed",
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Trip Plan] 发生错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


def _build_prompt(city, start_date, end_date, travel_days, transportation,
                   accommodation, preferences, extra_requirements,
                   pois_info, weather_info, hotels_info, budget_range=None):
    """构建 LLM 提示词"""
    # 预算信息
    budget_str = "无预算限制"
    budget_hint = ""
    if budget_range and len(budget_range) == 2:
        min_budget, max_budget = budget_range
        budget_str = f"{min_budget} - {max_budget} 元"
        # 根据预算给出提示
        if max_budget <= 1500:
            budget_hint = "\n注意：用户预算较紧张，请推荐免费或低价景点，选择经济实惠的餐饮和住宿。"
        elif max_budget <= 3000:
            budget_hint = "\n注意：用户预算适中，请合理安排景点门票，餐饮选择性价比高的餐厅。"
        elif max_budget <= 5000:
            budget_hint = "\n注意：用户预算充足，可以安排一些特色体验和品质餐饮。"
        else:
            budget_hint = "\n注意：用户预算宽裕，可以推荐高品质酒店和特色景点。"

    prompt = """你是一个专业的旅行规划师。请根据以下信息生成一份详细的旅行计划。

## 基本信息
- 城市: """ + city + """
- 日期范围: """ + start_date + """ 至 """ + end_date + """
- 旅行天数: """ + str(travel_days) + """ 天
- 交通方式: """ + transportation + """
- 住宿偏好: """ + accommodation + """
- 用户偏好: """ + preferences + """
- 预算范围: """ + budget_str + """
- 额外要求: """ + extra_requirements + budget_hint + """

## 可用景点 (请使用这些真实景点)
""" + pois_info + """

## 天气预报
""" + weather_info + """

## 可用酒店
""" + hotels_info + """

## 任务要求
1. 从可用景点中选择合适的景点，每天安排 2-3 个
2. 使用景点列表中提供的真实坐标 (longitude, latitude)
3. 为每天安排早餐、午餐、晚餐，价格要合理
4. 推荐合适的酒店，价格要在预算范围内
5. 生成的总预算必须严格控制在用户预算范围内
6. 门票、餐饮、住宿价格要参考实际情况，不要过高

请严格按照以下 JSON 格式输出，不要添加任何其他内容:

```json
{
  "city": "城市名",
  "start_date": "开始日期",
  "end_date": "结束日期",
  "days": [
    {
      "date": "日期YYYY-MM-DD",
      "day_index": 0,
      "description": "当日行程描述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 0, "latitude": 0},
        "price_range": "价格范围",
        "rating": "评分",
        "type": "酒店类型",
        "estimated_cost": 200
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "景点地址",
          "location": {"longitude": 116.4, "latitude": 39.9},
          "visit_duration": 120,
          "description": "景点描述",
          "category": "景点类别",
          "ticket_price": 50
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐", "description": "描述", "estimated_cost": 20},
        {"type": "lunch", "name": "午餐", "description": "描述", "estimated_cost": 40},
        {"type": "dinner", "name": "晚餐", "description": "描述", "estimated_cost": 60}
      ]
    }
  ],
  "weather_info": [],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 150,
    "total_hotels": 400,
    "total_meals": 300,
    "total_transportation": 50,
    "total": 900
  }
}
```
"""
    return prompt


@router.post("/plan/stream")
async def create_trip_plan_stream(request: TripRequest):
    """创建旅行计划 - 流式响应"""
    session_id = request.session_id or str(uuid.uuid4())

    print(f"\n{'='*60}")
    print(f"[Trip Plan Stream] 开始处理请求")
    print(f"[Trip Plan Stream] Session ID: {session_id}")
    print(f"[Trip Plan Stream] 城市: {request.city}")
    print(f"{'='*60}\n")

    async def event_generator():
        try:
            # Step 1: 初始化
            yield _create_sse_event(session_id, 1, "init", "running", "正在初始化...")

            amap = get_amap_service()
            pois = []
            search_keywords = request.preferences if request.preferences else ["景点"]

            # Step 2: POI搜索
            yield _create_sse_event(session_id, 2, "poi_search", "running",
                                    f"正在搜索景点: {', '.join(search_keywords[:3])}...")

            for i, keyword in enumerate(search_keywords[:3]):
                try:
                    yield _create_sse_event(session_id, 2, "poi_search", "running",
                                            f"正在搜索: {keyword} ({i+1}/{min(3, len(search_keywords))})")
                    result = await amap.search_poi(keyword, request.city, citylimit=True)
                    pois.extend(result)
                    yield _create_sse_event(session_id, 2, "poi_search", "running",
                                            f"已找到 {len(result)} 个 {keyword} 相关景点")
                except Exception as e:
                    print(f"POI搜索失败: {e}")
                    yield _create_sse_event(session_id, 2, "poi_search", "running",
                                            f"搜索 {keyword} 时出错: {str(e)}")

            seen = set()
            unique_pois = []
            for poi in pois:
                if poi.name not in seen:
                    seen.add(poi.name)
                    unique_pois.append(poi)

            yield _create_sse_event(session_id, 2, "poi_search", "completed",
                                    f"景点搜索完成，共找到 {len(unique_pois)} 个景点",
                                    {"pois_count": len(unique_pois)})

            # Step 3: 酒店搜索
            yield _create_sse_event(session_id, 3, "hotel", "running",
                                    f"正在搜索{request.accommodation}...")

            hotels = []
            try:
                hotels = await amap.search_hotels(request.city, request.accommodation)
                yield _create_sse_event(session_id, 3, "hotel", "completed",
                                        f"酒店搜索完成，找到 {len(hotels)} 家酒店",
                                        {"hotels_count": len(hotels)})
            except Exception as e:
                print(f"酒店搜索失败: {e}")
                yield _create_sse_event(session_id, 3, "hotel", "completed",
                                        f"酒店搜索完成（部分失败）")

            # Step 4: 天气查询
            yield _create_sse_event(session_id, 4, "weather", "running",
                                    "正在查询天气预报...")

            weather = []
            try:
                weather = await amap.get_weather(request.city)
                yield _create_sse_event(session_id, 4, "weather", "completed",
                                        f"天气查询完成，获取到 {len(weather)} 天预报",
                                        {"weather_days": len(weather)})
            except Exception as e:
                print(f"天气查询失败: {e}")
                yield _create_sse_event(session_id, 4, "weather", "completed",
                                        "天气查询完成（部分失败）")

            # Step 5: LLM 规划
            yield _create_sse_event(session_id, 5, "planner", "running",
                                    "正在构建行程规划提示词...")

            pois_info = _format_pois(unique_pois[:15])
            weather_info = _format_weather(weather)
            hotels_info = _format_hotels(hotels[:5])

            preferences_str = ', '.join(request.preferences) if request.preferences else '无特殊偏好'
            extra_requirements = request.free_text_input or '无'

            prompt = _build_prompt(
                city=request.city,
                start_date=request.start_date,
                end_date=request.end_date,
                travel_days=request.travel_days,
                transportation=request.transportation,
                accommodation=request.accommodation,
                preferences=preferences_str,
                extra_requirements=extra_requirements,
                pois_info=pois_info,
                weather_info=weather_info,
                hotels_info=hotels_info,
                budget_range=request.budget
            )

            yield _create_sse_event(session_id, 5, "planner", "running",
                                    f"正在调用 {request.llm_provider or 'deepseek'} 生成行程规划...")
            print(f"[Trip Plan Stream] 调用 LLM: {request.llm_provider}")

            llm = get_llm(request.llm_provider)
            response = await llm.ainvoke(prompt)

            yield _create_sse_event(session_id, 5, "planner", "running",
                                    "正在解析 AI 响应...")

            trip_plan = _parse_llm_response(response.content, request, unique_pois, hotels, weather)

            yield _create_sse_event(session_id, 5, "planner", "completed",
                                    f"行程规划完成，共 {len(trip_plan.get('days', []))} 天行程",
                                    {"plan_generated": True, "days_count": len(trip_plan.get('days', []))})

            # 保存结果到文件
            _save_trip_result(session_id, trip_plan, request)

            # Step 6: 完成
            yield _create_sse_event(session_id, 6, "complete", "completed",
                                    "行程规划已生成，正在跳转...",
                                    {"itinerary": trip_plan})

            print(f"[Trip Plan Stream] 完成，共 {len(trip_plan.get('days', []))} 天行程")

        except Exception as e:
            traceback.print_exc()
            yield _create_sse_event(session_id, 0, "error", "failed",
                                    f"执行失败: {str(e)}")

    return FastAPIStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


def _create_sse_event(session_id: str, step: int, node: str, status: str,
                       message: str, data: dict = None) -> str:
    """创建 SSE 事件"""
    event = {
        "session_id": session_id,
        "step": step,
        "node": node,
        "status": status,
        "message": message,
        "data": data or {}
    }
    return f"data: {json.dumps(event)}\n\n"


def _format_pois(pois: list) -> str:
    """格式化 POI 信息"""
    if not pois:
        return "暂无景点信息"

    lines = []
    for i, poi in enumerate(pois, 1):
        lines.append(f"{i}. {poi.name}")
        lines.append(f"   地址: {poi.address}")
        lines.append(f"   坐标: longitude={poi.location.longitude}, latitude={poi.location.latitude}")
        if poi.rating:
            lines.append(f"   评分: {poi.rating}")
        lines.append("")

    return "\n".join(lines)


def _format_weather(weather: list) -> str:
    """格式化天气信息"""
    if not weather:
        return "暂无天气信息"

    lines = []
    for w in weather:
        lines.append(f"{w.date}: {w.day_weather} {w.day_temp}°C / {w.night_weather} {w.night_temp}°C")

    return "\n".join(lines)


def _format_hotels(hotels: list) -> str:
    """格式化酒店信息"""
    if not hotels:
        return "暂无酒店信息"

    lines = []
    for i, h in enumerate(hotels, 1):
        lines.append(f"{i}. {h.name} - {h.address}")
        if h.rating:
            lines.append(f"   评分: {h.rating}")

    return "\n".join(lines)


def _parse_llm_response(response: str, request: TripRequest,
                        pois: list, hotels: list, weather: list) -> dict:
    """解析 LLM 响应"""
    import re
    from datetime import datetime, timedelta

    json_str = response

    # 尝试从 markdown 代码块中提取
    if "```json" in response:
        match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
        if match:
            json_str = match.group(1)
    elif "```" in response:
        match = re.search(r'```\s*([\s\S]*?)\s*```', response)
        if match:
            json_str = match.group(1)

    # 查找 JSON 对象
    start = json_str.find("{")
    if start >= 0:
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

    try:
        data = json.loads(json_str)

        if "city" not in data:
            data["city"] = request.city
        if "start_date" not in data:
            data["start_date"] = request.start_date
        if "end_date" not in data:
            data["end_date"] = request.end_date
        if "days" not in data or not data["days"]:
            data["days"] = _create_default_days(request, pois)

        # 确保每个景点有正确的坐标
        print(f"\n[Trip Plan] 开始处理景点坐标...")
        print(f"[Trip Plan] 可用POI数量: {len(pois)}")
        for poi in pois[:5]:
            if poi.location:
                print(f"[Trip Plan] POI: {poi.name} -> ({poi.location.longitude}, {poi.location.latitude})")

        for day_idx, day in enumerate(data.get("days", [])):
            print(f"[Trip Plan] 处理第{day_idx + 1}天景点...")
            for attr_idx, attr in enumerate(day.get("attractions", [])):
                attr_name = attr.get("name", "未知")
                print(f"[Trip Plan] 景点[{attr_idx}]: {attr_name}")
                print(f"[Trip Plan]   原始location: {attr.get('location')}")

                if "location" not in attr or not attr["location"]:
                    # 尝试从POI列表中匹配
                    found = False
                    for poi in pois:
                        if poi.name == attr_name or attr_name in poi.name or poi.name in attr_name:
                            if poi.location:
                                attr["location"] = {
                                    "longitude": poi.location.longitude,
                                    "latitude": poi.location.latitude
                                }
                                print(f"[Trip Plan]   从POI匹配到坐标: ({poi.location.longitude}, {poi.location.latitude})")
                                found = True
                                break
                    if not found:
                        print(f"[Trip Plan]   未找到匹配POI，使用默认坐标")
                        attr["location"] = {"longitude": 116.4, "latitude": 39.9}
                else:
                    # 验证坐标是否有效
                    loc = attr["location"]
                    lng = loc.get("longitude") or loc.get("lng")
                    lat = loc.get("latitude") or loc.get("lat")
                    if not lng or not lat or (lng == 0 and lat == 0):
                        print(f"[Trip Plan]   坐标无效，尝试从POI匹配...")
                        for poi in pois:
                            if poi.name == attr_name or attr_name in poi.name or poi.name in attr_name:
                                if poi.location:
                                    attr["location"] = {
                                        "longitude": poi.location.longitude,
                                        "latitude": poi.location.latitude
                                    }
                                    print(f"[Trip Plan]   从POI匹配到坐标: ({poi.location.longitude}, {poi.location.latitude})")
                                    break
                    else:
                        print(f"[Trip Plan]   坐标有效: ({lng}, {lat})")

        return data

    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        print(f"原始响应: {response[:1000]}")
        return {
            "city": request.city,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "days": _create_default_days(request, pois),
            "weather_info": [w.model_dump() for w in weather],
            "overall_suggestions": f"这是{request.city}的{request.travel_days}天旅行计划。",
            "budget": {
                "total_attractions": 200,
                "total_hotels": 900,
                "total_meals": 480,
                "total_transportation": 100,
                "total": 1680
            }
        }


def _create_default_days(request: TripRequest, pois: list) -> list:
    """创建默认行程"""
    from datetime import datetime, timedelta

    start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
    days = []

    attractions_per_day = 3
    poi_index = 0

    for i in range(request.travel_days):
        current_date = start_date + timedelta(days=i)

        day_attractions = []
        for j in range(attractions_per_day):
            if poi_index < len(pois):
                poi = pois[poi_index]
                day_attractions.append({
                    "name": poi.name,
                    "address": poi.address,
                    "location": {
                        "longitude": poi.location.longitude,
                        "latitude": poi.location.latitude
                    },
                    "visit_duration": 120,
                    "description": f"{request.city}推荐景点",
                    "category": poi.category or "景点",
                    "ticket_price": 50
                })
                poi_index += 1
            else:
                day_attractions.append({
                    "name": f"{request.city}景点{i*3+j+1}",
                    "address": f"{request.city}市中心",
                    "location": {"longitude": 116.4, "latitude": 39.9},
                    "visit_duration": 120,
                    "description": "推荐景点",
                    "category": "景点",
                    "ticket_price": 50
                })

        days.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "day_index": i,
            "description": f"第{i+1}天 - {request.city}游览",
            "transportation": request.transportation,
            "accommodation": request.accommodation,
            "attractions": day_attractions,
            "meals": [
                {"type": "breakfast", "name": "早餐", "description": "当地特色早餐", "estimated_cost": 30},
                {"type": "lunch", "name": "午餐", "description": "当地特色午餐", "estimated_cost": 50},
                {"type": "dinner", "name": "晚餐", "description": "当地特色晚餐", "estimated_cost": 80}
            ]
        })

    return days


@router.post("/feedback")
async def submit_feedback(feedback: UserFeedback):
    """提交用户反馈"""
    return {
        "success": True,
        "message": f"反馈已处理: {feedback.action}",
        "status": "completed"
    }


@router.get("/status/{session_id}")
async def get_trip_status(session_id: str):
    """获取旅行计划状态"""
    return {
        "session_id": session_id,
        "status": "completed",
        "current_node": "",
        "steps": [],
        "errors": [],
        "need_human_review": False
    }


@router.get("/result/{session_id}")
async def get_trip_result(session_id: str):
    """获取旅行计划结果"""
    return {
        "success": True,
        "message": "获取成功",
        "data": None,
        "status": "pending"
    }