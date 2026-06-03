"""路线优化服务 — 距离矩阵、TSP排序、偏好重排"""

import math
import asyncio
from typing import List, Optional, Dict, Tuple

from .amap_service import get_amap_service
from ..models.schemas import Location, POI, Attraction, RouteSegment


class RouteService:
    """路线规划和优化服务"""

    def __init__(self):
        self.amap = get_amap_service()

    async def build_distance_matrix(
        self,
        pois: List[POI],
        city: str,
        transport_mode: str = "walking"
    ) -> Dict[Tuple[int, int], RouteSegment]:
        """
        构建POI之间的距离/时间矩阵

        Args:
            pois: POI列表
            city: 城市名
            transport_mode: 交通方式

        Returns:
            Dict[(i, j), RouteSegment] — (起点索引, 终点索引) -> 路线段
        """
        matrix: Dict[Tuple[int, int], RouteSegment] = {}
        n = len(pois)

        print(f"\n[RouteService] 开始构建 {n}x{n} 距离矩阵, 交通方式: {transport_mode}")

        # 只为有坐标的POI计算
        valid_indices = [i for i, p in enumerate(pois) if p.location]

        if len(valid_indices) < 2:
            print("[RouteService] 有效坐标不足，跳过矩阵构建")
            return matrix

        # 按需调用路径规划（每对POI之间）
        tasks = []
        pairs = []
        for i in valid_indices:
            for j in valid_indices:
                if i == j:
                    continue
                pairs.append((i, j))
                tasks.append(self.amap.get_direction(
                    origin=pois[i].location,
                    destination=pois[j].location,
                    city=city,
                    transport_mode=transport_mode
                ))

        # 并发请求所有路径
        print(f"[RouteService] 并发请求 {len(tasks)} 条路径...")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for (i, j), result in zip(pairs, results):
            if isinstance(result, Exception):
                # 路径规划失败时，用直线距离估算
                print(f"[RouteService] ({i},{j}) 路径规划异常: {result}, 使用直线距离估算")
                segment = self._estimate_by_straight_line(pois[i].location, pois[j].location, transport_mode)
                if segment:
                    matrix[(i, j)] = segment
            elif result is not None:
                matrix[(i, j)] = result
            else:
                # 路径规划返回None时使用估算
                segment = self._estimate_by_straight_line(pois[i].location, pois[j].location, transport_mode)
                if segment:
                    matrix[(i, j)] = segment

        print(f"[RouteService] 距离矩阵构建完成, {len(matrix)} 条有效路径")
        return matrix

    def _estimate_by_straight_line(
        self,
        origin: Location,
        destination: Location,
        transport_mode: str
    ) -> Optional[RouteSegment]:
        """用直线距离估算路径"""
        # 使用Haversine公式计算距离
        R = 6371000  # 地球半径(米)

        lat1, lon1 = math.radians(origin.latitude), math.radians(origin.longitude)
        lat2, lon2 = math.radians(destination.latitude), math.radians(destination.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        # 根据交通方式估算时间
        if transport_mode == "driving" or transport_mode == "自驾":
            speed = 30 * 1000 / 60  # 30km/h -> m/min
            cost = self.amap._estimate_driving_cost(int(distance))
        elif transport_mode == "transit" or transport_mode == "公共交通":
            speed = 15 * 1000 / 60  # 15km/h -> m/min
            cost = 2.0
        else:
            speed = 5 * 1000 / 60  # 5km/h -> m/min
            cost = 0.0

        duration = max(1, int(distance / speed))

        return RouteSegment(
            from_poi="",
            to_poi="",
            from_location=origin,
            to_location=destination,
            distance_meters=int(distance),
            duration_minutes=duration,
            polyline="",
            transport_mode=transport_mode if transport_mode in ("driving", "walking", "transit") else "walking",
            cost_estimate=cost
        )

    def solve_tsp_greedy(
        self,
        pois: List[POI],
        matrix: Dict[Tuple[int, int], RouteSegment],
        start_index: int = 0
    ) -> List[int]:
        """
        贪心最近邻TSP求解

        从起点出发，每次选择距离最近且未访问的POI

        Args:
            pois: POI列表
            matrix: 距离矩阵
            start_index: 起点索引

        Returns:
            按访问顺序排列的POI索引列表
        """
        n = len(pois)
        if n <= 1:
            return list(range(n))

        unvisited = set(range(n))
        # 过滤掉没有坐标的POI
        unvisited = {i for i in unvisited if pois[i].location}

        if start_index not in unvisited:
            if unvisited:
                start_index = min(unvisited)
            else:
                return list(range(n))

        order = [start_index]
        unvisited.discard(start_index)

        while unvisited:
            current = order[-1]
            # 找最近的未访问POI
            nearest = None
            nearest_dist = float('inf')

            for candidate in unvisited:
                seg = matrix.get((current, candidate))
                if seg:
                    dist = seg.distance_meters
                else:
                    # 估算距离
                    if pois[current].location and pois[candidate].location:
                        loc1, loc2 = pois[current].location, pois[candidate].location
                        dist = self._haversine_distance(loc1, loc2)
                    else:
                        dist = float('inf')

                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest = candidate

            if nearest is None:
                break

            order.append(nearest)
            unvisited.discard(nearest)

        print(f"[RouteService] TSP贪心排序结果: {order}, 共{len(order)}个POI")
        return order

    def _haversine_distance(self, loc1: Location, loc2: Location) -> float:
        """计算两点间的Haversine距离(米)"""
        R = 6371000
        lat1, lon1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
        lat2, lon2 = math.radians(loc2.latitude), math.radians(loc2.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def build_route_segments(
        self,
        ordered_indices: List[int],
        pois: List[POI],
        matrix: Dict[Tuple[int, int], RouteSegment],
        start_location: Optional[Location] = None,
        end_location: Optional[Location] = None
    ) -> List[RouteSegment]:
        """
        根据排序结果构建完整的路线段列表

        Args:
            ordered_indices: 排序后的POI索引
            pois: POI列表
            matrix: 距离矩阵
            start_location: 用户出发位置
            end_location: 用户结束位置

        Returns:
            排序后的RouteSegment列表
        """
        segments = []

        # 构建每个相邻节点之间的路线段
        for k in range(len(ordered_indices)):
            if k == 0 and start_location:
                # 从用户出发位置到第一个POI
                seg = matrix.get((-1, ordered_indices[0]))
                if not seg:
                    seg = self._estimate_by_straight_line(
                        start_location,
                        pois[ordered_indices[0]].location,
                        "walking"
                    )
                if seg:
                    seg.from_poi = "出发地点"
                    seg.to_poi = pois[ordered_indices[0]].name
                    segments.append(seg)

            if k < len(ordered_indices) - 1:
                i, j = ordered_indices[k], ordered_indices[k + 1]
                seg = matrix.get((i, j))
                if seg:
                    seg.from_poi = pois[i].name
                    seg.to_poi = pois[j].name
                    segments.append(seg)
                elif pois[i].location and pois[j].location:
                    # 矩阵中没有，用估算
                    seg = self._estimate_by_straight_line(pois[i].location, pois[j].location, "walking")
                    if seg:
                        seg.from_poi = pois[i].name
                        seg.to_poi = pois[j].name
                        segments.append(seg)

        return segments

    def calculate_optimization_metrics(
        self,
        segments: List[RouteSegment],
        total_duration_minutes: int,
        time_budget_minutes: int,
        budget_total: float,
        budget_range: Optional[List[int]],
        preference_match_score: float = 70.0
    ) -> Dict[str, float]:
        """
        计算路线优化指标

        Args:
            segments: 路线段列表
            total_duration_minutes: 总耗时
            time_budget_minutes: 时间预算
            budget_total: 总费用
            budget_range: 预算范围
            preference_match_score: 偏好匹配分

        Returns:
            各指标分数字典
        """
        # 时间效率: 实际耗时不超时间预算得高分
        if time_budget_minutes > 0:
            time_efficiency = max(0, 100 - (total_duration_minutes / time_budget_minutes * 100))
            time_efficiency = min(100, time_efficiency + 20)  # 轻微宽容
        else:
            time_efficiency = 80.0

        # 费用效率
        if budget_range and len(budget_range) == 2:
            budget_max = budget_range[1]
            if budget_max > 0:
                cost_efficiency = max(0, 100 - (budget_total / budget_max * 100))
                cost_efficiency = min(100, cost_efficiency + 10)
            else:
                cost_efficiency = 80.0
        else:
            cost_efficiency = 80.0

        # 路线合理性: 总距离合理、无重叠
        if segments:
            unique_pois = set()
            for seg in segments:
                unique_pois.add(seg.from_poi)
                unique_pois.add(seg.to_poi)
            route_coherence = min(100, len(unique_pois) * 12)
        else:
            route_coherence = 50.0

        # 综合评分: 加权平均
        overall = (
            time_efficiency * 0.3 +
            cost_efficiency * 0.25 +
            preference_match_score * 0.25 +
            route_coherence * 0.2
        )

        return {
            "time_efficiency": round(time_efficiency, 1),
            "cost_efficiency": round(cost_efficiency, 1),
            "preference_match": round(preference_match_score, 1),
            "route_coherence": round(route_coherence, 1),
            "overall_score": round(overall, 1)
        }


# 单例
_route_service: Optional[RouteService] = None


def get_route_service() -> RouteService:
    """获取路线服务实例"""
    global _route_service
    if _route_service is None:
        _route_service = RouteService()
    return _route_service
