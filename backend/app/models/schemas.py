"""数据模型定义"""

from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
import uuid


# ===========================================
# 枚举类型
# ===========================================

class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    ALIYUN = "aliyun"
    OPENAI = "openai"


class TripStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEED_CONFIRM = "need_confirm"  # Human-in-the-loop


class NodeType(str, Enum):
    ROUTER = "router"
    POI_SEARCH = "poi_search"
    WEATHER = "weather"
    HOTEL = "hotel"
    PLANNER = "planner"
    HUMAN_REVIEW = "human_review"
    INTENT_ANALYSIS = "intent_analysis"
    REVIEW_ENRICH = "review_enrich"
    ROUTE_OPTIMIZER = "route_optimizer"
    BUDGET_VALIDATOR = "budget_validator"
    ITINERARY_GENERATOR = "itinerary_generator"


# ===========================================
# 基础数据模型
# ===========================================

class Location(BaseModel):
    """地理位置"""
    longitude: float = Field(..., description="经度")
    latitude: float = Field(..., description="纬度")


class POI(BaseModel):
    """兴趣点"""
    id: str = Field(default="", description="POI ID")
    name: str = Field(..., description="名称")
    address: str = Field(default="", description="地址")
    location: Optional[Location] = Field(default=None, description="坐标")
    category: Optional[str] = Field(default=None, description="类别")
    rating: Optional[float] = Field(default=None, description="评分")
    tel: Optional[str] = Field(default=None, description="电话")
    ticket_price: Optional[int] = Field(default=0, description="门票价格")
    visit_duration: Optional[int] = Field(default=120, description="建议游览时长(分钟)")
    description: Optional[str] = Field(default=None, description="描述")
    image_url: Optional[str] = Field(default=None, description="图片URL")
    popularity_score: Optional[float] = Field(default=None, description="热度评分 0-100")
    queue_time_min: Optional[int] = Field(default=None, description="预估排队时间(分钟)")


class Review(BaseModel):
    """UGC 用户评价"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], description="评价ID")
    poi_name: str = Field(..., description="关联POI名称")
    user_name: str = Field(default="匿名用户", description="用户名")
    rating: float = Field(..., ge=1, le=5, description="评分 1-5")
    content: str = Field(..., description="评价内容")
    date: str = Field(default="", description="评价日期")
    sentiment: str = Field(default="neutral", description="情感: positive/neutral/negative")
    tags: List[str] = Field(default_factory=list, description="标签,如 ['排队快','性价比高','环境好']")
    like_count: int = Field(default=0, description="点赞数")


class Weather(BaseModel):
    """天气信息"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    day_weather: str = Field(default="", description="白天天气")
    night_weather: str = Field(default="", description="夜间天气")
    day_temp: Union[int, str] = Field(default=0, description="白天温度")
    night_temp: Union[int, str] = Field(default=0, description="夜间温度")
    wind_direction: str = Field(default="", description="风向")
    wind_power: str = Field(default="", description="风力")


class Hotel(BaseModel):
    """酒店信息"""
    name: str = Field(..., description="酒店名称")
    address: str = Field(default="", description="地址")
    location: Optional[Location] = Field(default=None, description="坐标")
    price_range: str = Field(default="", description="价格范围")
    rating: str = Field(default="", description="评分")
    type: str = Field(default="", description="酒店类型")
    estimated_cost: int = Field(default=0, description="预估费用")


class Meal(BaseModel):
    """餐饮信息"""
    type: str = Field(..., description="类型: breakfast/lunch/dinner")
    name: str = Field(..., description="名称")
    address: Optional[str] = Field(default=None, description="地址")
    description: Optional[str] = Field(default=None, description="描述")
    estimated_cost: int = Field(default=0, description="预估费用")


class Attraction(BaseModel):
    """景点信息（行程中的景点）"""
    name: str = Field(..., description="名称")
    address: str = Field(..., description="地址")
    location: Location = Field(..., description="坐标")
    visit_duration: int = Field(default=120, description="游览时长(分钟)")
    description: str = Field(default="", description="描述")
    category: Optional[str] = Field(default=None, description="类别")
    ticket_price: int = Field(default=0, description="门票价格")


class RouteSegment(BaseModel):
    """路线段 — 两个POI之间的路径"""
    from_poi: str = Field(..., description="起点POI名称")
    to_poi: str = Field(..., description="终点POI名称")
    from_location: Location = Field(..., description="起点坐标")
    to_location: Location = Field(..., description="终点坐标")
    distance_meters: int = Field(default=0, description="距离(米)")
    duration_minutes: int = Field(default=0, description="耗时(分钟)")
    polyline: str = Field(default="", description="高德路径编码polyline")
    transport_mode: str = Field(default="walking", description="交通方式: driving/walking/transit")
    cost_estimate: float = Field(default=0.0, description="预估费用(元)")


class DayPlan(BaseModel):
    """单日行程"""
    date: str = Field(..., description="日期")
    day_index: int = Field(..., description="第几天(从0开始)")
    description: str = Field(..., description="当日描述")
    transportation: str = Field(default="", description="交通方式")
    accommodation: str = Field(default="", description="住宿")
    hotel: Optional[Hotel] = Field(default=None, description="推荐酒店")
    attractions: List[Attraction] = Field(default_factory=list, description="景点列表")
    meals: List[Meal] = Field(default_factory=list, description="餐饮列表")


class Budget(BaseModel):
    """预算信息"""
    total_attractions: int = Field(default=0, description="景点门票总费用")
    total_hotels: int = Field(default=0, description="酒店总费用")
    total_meals: int = Field(default=0, description="餐饮总费用")
    total_transportation: int = Field(default=0, description="交通总费用")
    total: int = Field(default=0, description="总费用")


class OptimizationMetrics(BaseModel):
    """路线优化指标"""
    time_efficiency: float = Field(default=0.0, ge=0, le=100, description="时间效率分")
    cost_efficiency: float = Field(default=0.0, ge=0, le=100, description="费用效率分")
    preference_match: float = Field(default=0.0, ge=0, le=100, description="偏好匹配分")
    route_coherence: float = Field(default=0.0, ge=0, le=100, description="路线合理性分")
    overall_score: float = Field(default=0.0, ge=0, le=100, description="综合评分")


class RoutePlan(BaseModel):
    """本地单日路线方案"""
    city: str = Field(..., description="城市")
    date: str = Field(..., description="日期")
    start_location: Optional[Location] = Field(default=None, description="出发地点")
    start_time: Optional[str] = Field(default=None, description="出发时间")
    ordered_pois: List[Attraction] = Field(default_factory=list, description="排序后的POI列表")
    route_segments: List[RouteSegment] = Field(default_factory=list, description="路线段列表")
    total_distance_km: float = Field(default=0.0, description="总距离(公里)")
    total_duration_minutes: int = Field(default=0, description="总耗时(分钟)")
    total_cost: float = Field(default=0.0, description="总预估费用")
    optimization_metrics: Optional[OptimizationMetrics] = Field(default=None, description="优化指标")
    meals: List[Meal] = Field(default_factory=list, description="餐饮推荐")
    weather: Optional[Weather] = Field(default=None, description="当日天气")
    suggestions: str = Field(default="", description="总体建议")
    trade_off_explanations: List[str] = Field(default_factory=list, description="路线取舍说明")


class TripPlan(BaseModel):
    """旅行计划"""
    city: str = Field(..., description="城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    days: List[DayPlan] = Field(default_factory=list, description="每日行程")
    weather_info: List[Weather] = Field(default_factory=list, description="天气信息")
    overall_suggestions: str = Field(default="", description="总体建议")
    budget: Optional[Budget] = Field(default=None, description="预算信息")


class UserProfile(BaseModel):
    """用户偏好画像"""
    user_id: str = Field(..., description="用户ID")
    preferred_categories: Dict[str, float] = Field(default_factory=dict, description="偏好类别权重")
    budget_preference: str = Field(default="moderate", description="预算偏好: economy/moderate/luxury")
    transport_preference: str = Field(default="公共交通", description="交通偏好")
    visit_history: List[str] = Field(default_factory=list, description="访问历史(POI名称)")
    review_sentiment_preferences: Dict[str, float] = Field(default_factory=dict, description="评价情感偏好")
    preferred_poi_ids: List[str] = Field(default_factory=list, description="收藏的POI ID列表")
    avoided_poi_ids: List[str] = Field(default_factory=list, description="避开的POI ID列表")
    last_updated: Optional[datetime] = Field(default=None, description="最后更新时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


# ===========================================
# 请求模型
# ===========================================

class TripRequest(BaseModel):
    """旅行规划请求"""
    session_id: str = Field(default="", description="会话ID")
    city: str = Field(..., description="目的地城市")
    start_date: str = Field(..., description="开始日期")
    end_date: str = Field(..., description="结束日期")
    travel_days: int = Field(..., ge=1, le=30, description="旅行天数")
    transportation: str = Field(default="公共交通", description="交通方式")
    accommodation: str = Field(default="经济型酒店", description="住宿偏好")
    preferences: List[str] = Field(default_factory=list, description="旅行偏好")
    free_text_input: Optional[str] = Field(default="", description="额外要求")
    llm_provider: Optional[str] = Field(default=None, description="指定LLM提供商")
    budget: Optional[List[int]] = Field(default=None, description="预算范围 [最小值, 最大值]")


class LocalRouteRequest(BaseModel):
    """本地路线规划请求"""
    session_id: str = Field(default="", description="会话ID")
    user_id: Optional[str] = Field(default=None, description="用户ID(用于个性化)")
    city: str = Field(..., description="目标城市")
    date: str = Field(..., description="出行日期 YYYY-MM-DD")
    start_location: Optional[Location] = Field(default=None, description="出发地点坐标")
    start_address: Optional[str] = Field(default=None, description="出发地址文字描述")
    start_time: Optional[str] = Field(default="09:00", description="出发时间 HH:MM")
    end_time: Optional[str] = Field(default="18:00", description="结束时间 HH:MM")
    transportation: str = Field(default="公共交通", description="交通方式: 公共交通/自驾/步行/混合")
    preferences: List[str] = Field(default_factory=list, description="偏好标签")
    free_text_input: Optional[str] = Field(default="", description="额外文字要求")
    budget: Optional[List[int]] = Field(default=None, description="预算范围 [最小值, 最大值]")
    llm_provider: Optional[str] = Field(default=None, description="指定LLM提供商")
    poi_count: int = Field(default=4, ge=2, le=10, description="期望访问POI数量")


class ChatMessage(BaseModel):
    """聊天消息"""
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="消息内容")
    message_type: str = Field(default="text", description="消息类型")
    llm_provider: Optional[str] = Field(default=None, description="LLM提供商")


class UserFeedback(BaseModel):
    """用户反馈 (Human-in-the-loop)"""
    session_id: str = Field(..., description="会话ID")
    action: str = Field(..., description="动作: approve/modify/reject")
    modifications: Optional[Dict[str, Any]] = Field(default=None, description="修改内容")
    comment: Optional[str] = Field(default=None, description="评论")


# ===========================================
# 响应模型
# ===========================================

class TripPlanResponse(BaseModel):
    """旅行计划响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="消息")
    data: Optional[TripPlan] = Field(default=None, description="旅行计划")
    route_plan: Optional[RoutePlan] = Field(default=None, description="本地路线方案")
    status: TripStatus = Field(default=TripStatus.PENDING, description="状态")


class AgentStep(BaseModel):
    """Agent 执行步骤"""
    node: str = Field(..., description="节点名称")
    status: str = Field(..., description="状态")
    input: Optional[Dict[str, Any]] = Field(default=None, description="输入")
    output: Optional[Dict[str, Any]] = Field(default=None, description="输出")
    duration_ms: Optional[int] = Field(default=None, description="耗时(毫秒)")
    error: Optional[str] = Field(default=None, description="错误信息")


class StreamingResponse(BaseModel):
    """流式响应"""
    session_id: str = Field(..., description="会话ID")
    step: int = Field(..., description="步骤序号")
    node: str = Field(..., description="当前节点")
    status: TripStatus = Field(..., description="状态")
    message: str = Field(default="", description="消息")
    data: Optional[Dict[str, Any]] = Field(default=None, description="数据")
    thought: Optional[str] = Field(default=None, description="Agent 思考过程")
    steps: List[AgentStep] = Field(default_factory=list, description="执行步骤列表")


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str = Field(..., description="会话ID")
    response: str = Field(..., description="响应内容")
    trip_plan: Optional[TripPlan] = Field(default=None, description="旅行计划(如果有)")


# ===========================================
# Agent 状态模型 (LangGraph State)
# ===========================================



class AgentState(BaseModel):
    """Agent 状态 - LangGraph 使用"""
    # 基本信息
    session_id: str = Field(default="", description="会话ID")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    city: str = Field(default="", description="城市")
    start_date: str = Field(default="", description="开始日期")
    end_date: str = Field(default="", description="结束日期")
    date: str = Field(default="", description="出行日期(本地路线)")
    travel_days: int = Field(default=1, description="旅行天数")
    transportation: str = Field(default="公共交通", description="交通方式")
    accommodation: str = Field(default="经济型酒店", description="住宿偏好")
    preferences: List[str] = Field(default_factory=list, description="旅行偏好")
    free_text_input: str = Field(default="", description="额外要求")
    budget: Optional[List[int]] = Field(default=None, description="预算范围")
    poi_count: int = Field(default=4, description="POI数量")
    start_time: str = Field(default="09:00", description="出发时间")
    end_time: str = Field(default="18:00", description="结束时间")
    start_address: Optional[str] = Field(default=None, description="出发地址")
    start_location: Optional[Dict[str, Any]] = Field(default=None, description="出发坐标")

    # 意图分析
    intent: Dict[str, Any] = Field(default_factory=dict, description="意图分析结果")
    user_profile: Optional[Dict[str, Any]] = Field(default=None, description="用户画像")

    # Agent 输出
    pois: List[POI] = Field(default_factory=list, description="POI列表")
    weather: List[Weather] = Field(default_factory=list, description="天气信息")
    hotels: List[Hotel] = Field(default_factory=list, description="酒店列表")
    itinerary: Optional[Dict[str, Any]] = Field(default=None, description="行程/路线方案(可为TripPlan或RoutePlan)")

    # 路线优化输出
    route_segments: List[Dict[str, Any]] = Field(default_factory=list, description="路线段列表")
    ordered_pois: List[Dict[str, Any]] = Field(default_factory=list, description="排序后的POI")
    optimization_metrics: Dict[str, Any] = Field(default_factory=dict, description="优化指标")
    total_distance_km: float = Field(default=0.0, description="总距离(km)")
    total_duration_minutes: int = Field(default=0, description="总耗时(分钟)")
    total_cost: float = Field(default=0.0, description="总费用")
    time_budget_minutes: int = Field(default=480, description="时间预算(分钟)")
    budget_valid: Optional[bool] = Field(default=None, description="预算是否有效")

    # 执行状态
    current_node: str = Field(default="", description="当前节点")
    status: TripStatus = Field(default=TripStatus.PENDING, description="状态")
    steps: List[AgentStep] = Field(default_factory=list, description="执行步骤")
    errors: List[str] = Field(default_factory=list, description="错误列表")

    # Human-in-the-loop
    need_human_review: bool = Field(default=False, description="是否需要人工审核")
    human_feedback: Optional[str] = Field(default=None, description="人工反馈")

    # 元数据
    llm_provider: str = Field(default="deepseek", description="LLM提供商")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Config:
        extra = "allow"  # 允许额外字段，防止丢失未定义的图状态字段
