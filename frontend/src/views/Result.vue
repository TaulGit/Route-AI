<template>
  <div class="result-container">
    <!-- 头部 -->
    <div class="header">
      <el-button @click="$router.push('/')" text>
        <el-icon><ArrowLeft /></el-icon>
        返回首页
      </el-button>
      <div class="header-title-block">
        <h1>{{ tripStore.title || (tripStore.isLocalRoute ? '🗺️ 路线规划结果' : '📋 行程规划结果') }}</h1>
        <p v-if="tripStore.sessionId" class="session-note">会话 ID：{{ tripStore.sessionId }}</p>
      </div>
      <div class="header-actions">
        <el-button @click="$router.push('/history')">历史记录</el-button>
        <el-button type="primary" @click="handleExportPDF">
          <el-icon><Download /></el-icon>
          导出PDF
        </el-button>
        <el-button @click="handleReset">
          <el-icon><Refresh /></el-icon>
          重新规划
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="!hasData" class="empty-state">
      <el-empty description="暂无行程数据">
        <el-button type="primary" @click="$router.push('/')">开始规划</el-button>
      </el-empty>
    </div>

    <!-- 行程内容 -->
    <div v-else class="content">
      <!-- 概览卡片 -->
      <el-card class="overview-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Location /></el-icon>
            <span>行程概览</span>
          </div>
        </template>
        <!-- 本地路线模式 -->
        <el-descriptions v-if="tripStore.isLocalRoute" :column="4" border>
          <el-descriptions-item label="目的地">{{ cityName }}</el-descriptions-item>
          <el-descriptions-item label="出行日期">{{ routeDate }}</el-descriptions-item>
          <el-descriptions-item label="POI数量">{{ tripStore.orderedPois.length }}个</el-descriptions-item>
          <el-descriptions-item label="交通方式">{{ transportMode }}</el-descriptions-item>
        </el-descriptions>
        <!-- 旅行规划模式 -->
        <el-descriptions v-else :column="4" border>
          <el-descriptions-item label="目的地">{{ tripPlan?.city }}</el-descriptions-item>
          <el-descriptions-item label="出发日期">{{ tripPlan?.start_date }}</el-descriptions-item>
          <el-descriptions-item label="返回日期">{{ tripPlan?.end_date }}</el-descriptions-item>
          <el-descriptions-item label="行程天数">{{ tripPlan?.days?.length || 0 }}天</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 地图展示 -->
      <el-card v-if="tripStore.isLocalRoute" class="map-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><MapLocation /></el-icon>
            <span>景点地图</span>
          </div>
        </template>
        <div id="map-container" class="map-container"></div>
      </el-card>

      <!-- ==================== 本地路线模式 ==================== -->
      <template v-if="tripStore.isLocalRoute">
        <!-- 路线概览 -->
        <el-card v-if="tripStore.routeSegments.length > 0" class="route-overview-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Guide /></el-icon>
              <span>路线概览</span>
            </div>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="路线段数">{{ tripStore.routeSegments.length }}段</el-descriptions-item>
            <el-descriptions-item label="总距离">{{ getTotalDistance().toFixed(1) }} km</el-descriptions-item>
            <el-descriptions-item label="路程时间">{{ getTotalDuration() }} 分钟</el-descriptions-item>
            <el-descriptions-item label="预估费用">¥{{ getTotalCost().toFixed(0) }}</el-descriptions-item>
          </el-descriptions>

          <!-- 出发地点 -->
          <div v-if="(tripPlan as any)?.start_name" class="route-start-point">
            🚩 出发：{{ (tripPlan as any).start_name }}
          </div>

          <div v-if="tripStore.orderedPois.length > 0" class="route-timeline">
            <h4>📍 路线顺序</h4>
            <el-timeline>
              <el-timeline-item
                v-for="(poi, idx) in tripStore.orderedPois"
                :key="idx"
                :type="idx === 0 ? 'primary' : 'success'"
                :hollow="idx > 0"
              >
                <div class="route-poi-item">
                  <el-tag size="small" type="primary">第{{ idx + 1 }}站</el-tag>
                  <span class="poi-name">{{ poi.name }}</span>
                  <span v-if="tripStore.routeSegments[idx - 1]" class="route-info">
                    ← {{ (tripStore.routeSegments[idx - 1].distance_meters / 1000).toFixed(1) }}km
                    / {{ tripStore.routeSegments[idx - 1].duration_minutes }}min
                    {{ tripStore.routeSegments[idx - 1].transport_mode === 'driving' ? '🚗' : tripStore.routeSegments[idx - 1].transport_mode === 'transit' ? '🚌' : '🚶' }}
                  </span>
                </div>
                <div class="poi-detail" v-if="poi.address">
                  <span>📍 {{ poi.address }}</span>
                  <span v-if="poi.visit_duration"> | 🕐 {{ poi.visit_duration }}分钟</span>
                  <span v-if="poi.ticket_price"> | 🎫 ¥{{ poi.ticket_price }}</span>
                  <span v-if="poi.rating"> | ⭐ {{ poi.rating }}</span>
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-card>

        <!-- 餐饮推荐 -->
        <el-card v-if="routePlanData?.meals?.length" class="meals-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Food /></el-icon>
              <span>餐饮推荐</span>
            </div>
          </template>
          <el-row :gutter="12">
            <el-col v-for="(meal, mi) in routePlanData.meals" :key="mi" :span="8">
              <el-card shadow="hover" class="meal-card">
                <div class="meal-type">{{ meal.type === 'breakfast' ? '🌅 早餐' : meal.type === 'lunch' ? '☀️ 午餐' : '🌙 晚餐' }}</div>
                <div class="meal-name">{{ meal.name }}</div>
                <div class="meal-desc">{{ meal.description }}</div>
                <div v-if="meal.estimated_cost" class="meal-price">¥{{ meal.estimated_cost }}</div>
              </el-card>
            </el-col>
          </el-row>
        </el-card>

        <!-- 建议 -->
        <el-card v-if="routePlanData?.suggestions" class="tips-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Warning /></el-icon>
              <span>路线建议</span>
            </div>
          </template>
          <p class="tips-text">{{ routePlanData.suggestions }}</p>
          <div v-if="routePlanData?.trade_off_explanations?.length" class="tips-tags">
            <el-tag v-for="(t, ti) in routePlanData.trade_off_explanations" :key="ti">{{ t }}</el-tag>
          </div>
        </el-card>

        <!-- 路线指标（低调版） -->
        <div v-if="tripStore.optimizationMetrics" class="metrics-subtle">
          <span class="metrics-label">路线评分</span>
          <span v-if="tripStore.optimizationMetrics.overall_score" class="metrics-main">{{ tripStore.optimizationMetrics.overall_score }}分</span>
          <el-divider direction="vertical" />
          <span>时间 {{ tripStore.optimizationMetrics.time_efficiency }}%</span>
          <el-divider direction="vertical" />
          <span>费用 {{ tripStore.optimizationMetrics.cost_efficiency }}%</span>
          <el-divider direction="vertical" />
          <span>偏好 {{ tripStore.optimizationMetrics.preference_match }}%</span>
          <el-divider direction="vertical" />
          <span>路径 {{ tripStore.optimizationMetrics.route_coherence }}%</span>
        </div>
      </template>

      <!-- ==================== 旅行规划模式 ==================== -->
      <template v-else>
        <!-- 每日行程 -->
        <el-card class="itinerary-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Calendar /></el-icon>
              <span>每日行程</span>
            </div>
          </template>
          <el-collapse v-model="activeDays" @change="handleDayCollapseChange">
            <el-collapse-item v-for="(day, index) in tripPlan?.days" :key="index" :name="index">
              <template #title>
                <div class="day-title">
                  <el-tag type="primary">第{{ day.day_index + 1 }}天</el-tag>
                  <span class="day-date">{{ day.date }}</span>
                  <span class="day-theme">{{ day.description }}</span>
                </div>
              </template>
              <div v-if="day.attractions?.length" class="day-map-block">
                <div class="day-map-header">
                  <el-icon><MapLocation /></el-icon>
                  <span>第{{ day.day_index + 1 }}天地图</span>
                </div>
                <div :id="`trip-day-map-${index}`" class="map-container day-map-container"></div>
              </div>
              <el-timeline>
                <el-timeline-item v-for="(attraction, attrIndex) in day.attractions" :key="attrIndex" placement="top">
                  <el-card class="spot-card">
                    <div class="spot-header">
                      <h4>{{ attraction.name }}</h4>
                      <el-tag v-if="attraction.category" size="small">{{ attraction.category }}</el-tag>
                    </div>
                    <div class="spot-info">
                      <p v-if="attraction.description">{{ attraction.description }}</p>
                      <div class="spot-details">
                        <span v-if="attraction.visit_duration"><el-icon><Clock /></el-icon> 游玩时长: {{ attraction.visit_duration }}分钟</span>
                        <span v-if="attraction.ticket_price"><el-icon><Ticket /></el-icon> 门票: ¥{{ attraction.ticket_price }}</span>
                      </div>
                      <div class="spot-address"><el-icon><Location /></el-icon> {{ attraction.address }}</div>
                    </div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
              <div v-if="day.meals?.length" class="dining-section">
                <h4><el-icon><Food /></el-icon> 餐饮推荐</h4>
                <el-row :gutter="12">
                  <el-col v-for="(meal, mi) in day.meals" :key="mi" :span="8">
                    <el-card shadow="hover" class="meal-card">
                      <div class="meal-type">{{ meal.type === 'breakfast' ? '早餐' : meal.type === 'lunch' ? '午餐' : '晚餐' }}</div>
                      <div class="meal-name">{{ meal.name }}</div>
                      <div class="meal-desc">{{ meal.description }}</div>
                      <div v-if="meal.estimated_cost" class="meal-price">¥{{ meal.estimated_cost }}</div>
                    </el-card>
                  </el-col>
                </el-row>
              </div>
              <div v-if="day.hotel" class="accommodation-section">
                <h4><el-icon><House /></el-icon> 住宿安排</h4>
                <el-card shadow="hover">
                  <div class="hotel-name">{{ day.hotel.name }}</div>
                  <div class="hotel-details">
                    <span v-if="day.hotel.type">{{ day.hotel.type }}</span>
                    <span v-if="day.hotel.price_range">{{ day.hotel.price_range }}</span>
                    <span v-if="day.hotel.rating"><el-icon><Star /></el-icon> {{ day.hotel.rating }}</span>
                  </div>
                  <div v-if="day.hotel.address" class="hotel-address"><el-icon><Location /></el-icon> {{ day.hotel.address }}</div>
                </el-card>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>

        <!-- 预算 -->
        <el-card v-if="tripPlan?.budget" class="budget-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Wallet /></el-icon>
              <span>预算估算</span>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="6"><el-statistic title="景点门票" :value="tripPlan.budget.total_attractions" suffix="元" /></el-col>
            <el-col :span="6"><el-statistic title="住宿费用" :value="tripPlan.budget.total_hotels" suffix="元" /></el-col>
            <el-col :span="6"><el-statistic title="餐饮费用" :value="tripPlan.budget.total_meals" suffix="元" /></el-col>
            <el-col :span="6"><el-statistic title="交通费用" :value="tripPlan.budget.total_transportation" suffix="元" /></el-col>
          </el-row>
          <el-divider />
          <el-statistic title="总预算" :value="tripPlan.budget.total" suffix="元" class="total-budget" />
        </el-card>

        <!-- 建议 -->
        <el-card v-if="tripPlan?.overall_suggestions" class="tips-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Warning /></el-icon>
              <span>旅行建议</span>
            </div>
          </template>
          <p class="tips-text">{{ tripPlan.overall_suggestions }}</p>
        </el-card>
      </template>
    </div>

    <!-- 人工审核对话框 -->
    <el-dialog v-model="showReviewDialog" title="行程确认" width="600px">
      <div class="review-content">
        <el-alert title="请确认您的行程安排" type="warning" description="AI已为您生成行程规划，请仔细核对后确认。" :closable="false" show-icon />
        <div class="review-actions">
          <el-input v-model="reviewComment" type="textarea" :rows="3" placeholder="如有修改意见，请在此输入..." />
        </div>
      </div>
      <template #footer>
        <el-button @click="handleReject">重新规划</el-button>
        <el-button type="primary" @click="handleApprove">确认行程</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ArrowLeft, Download, Refresh, Location, MapLocation, Calendar,
  Clock, Ticket, Star, Food, House, Wallet, Warning,
  Guide
} from '@element-plus/icons-vue'
import { useTripStore } from '@/stores/trip'
import { approveTripPlan, rejectTripPlan } from '@/services/api'

const router = useRouter()
const tripStore = useTripStore()

// 双模式: TripPlan（旅行）或 RoutePlan（本地路线）
const tripPlan = computed(() => tripStore.tripPlan)
const routePlanData = computed(() => tripStore.tripPlan as any)  // 本地路线模式时 tripPlan 实际存的是 RoutePlan
const hasData = computed(() => {
  if (tripStore.isLocalRoute) {
    return tripStore.orderedPois.length > 0 || !!tripStore.tripPlan
  }
  return !!tripStore.tripPlan
})

// 本地路线模式的派生数据
const cityName = computed(() => tripStore.tripPlan?.city || tripStore.orderedPois[0]?.address || '')
const routeDate = computed(() => (tripStore.tripPlan as any)?.date || (tripStore.tripPlan as any)?.start_date || '')
const TRANSPORT_CN: Record<string, string> = { driving: '驾车', walking: '步行', transit: '公交' }
const transportMode = computed(() => {
  const modes = [...new Set(tripStore.routeSegments.map(s => s.transport_mode))]
  return modes.map(m => TRANSPORT_CN[m] || m).join(' + ') || '步行'
})

const activeDays = ref<number[]>([0])
const showReviewDialog = ref(false)
const reviewComment = ref('')
const mapInstance = ref<any>(null)
const tripDayMaps = ref<any[]>([])
const mapLoaded = ref(false)

function getTotalDistance(): number {
  return tripStore.routeSegments.reduce((sum, s) => sum + s.distance_meters, 0) / 1000
}
function getTotalDuration(): number {
  return tripStore.routeSegments.reduce((sum, s) => sum + s.duration_minutes, 0)
}
function getTotalCost(): number {
  return tripStore.routeSegments.reduce((sum, s) => sum + (s.cost_estimate || 0), 0)
}

async function initMap() {
  const city = cityName.value
  if (!city) return

  await nextTick()
  const hasContainer = tripStore.isLocalRoute
    ? !!document.getElementById('map-container')
    : !!document.querySelector('[id^="trip-day-map-"]')
  if (!hasContainer) return

  const amapKey = (import.meta as any).env?.VITE_AMAP_KEY
  if (!amapKey) return

  const AMap = (window as any).AMap
  if (!AMap) {
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=1.4.15&key=${amapKey}&plugin=AMap.Geocoder,AMap.Scale,AMap.ToolBar,AMap.Driving,AMap.Walking`
    script.onload = () => {
      mapLoaded.value = true
      setTimeout(() => {
        if (tripStore.isLocalRoute) {
          createMap()
        } else {
          createTripDayMaps()
        }
      }, 100)
    }
    document.head.appendChild(script)
  } else {
    mapLoaded.value = true
    if (tripStore.isLocalRoute) {
      createMap()
    } else {
      createTripDayMaps()
    }
  }
}

async function createTripDayMaps() {
  const AMap = (window as any).AMap
  if (!AMap || !tripPlan.value?.days?.length) return

  tripDayMaps.value.forEach(map => {
    if (map?.destroy) map.destroy()
  })
  tripDayMaps.value = []

  for (const [index, day] of tripPlan.value.days.entries()) {
    const containerId = `trip-day-map-${index}`
    const container = document.getElementById(containerId)
    if (!container || !day.attractions?.length) continue

    const dayPoints = day.attractions
      .map((attraction: any) => {
        const loc = attraction.location
        if (!loc) return null
        const lng = loc.longitude || loc.lng
        const lat = loc.latitude || loc.lat
        if (!lng || !lat || (lng === 0 && lat === 0)) return null
        return {
          ...attraction,
          lng,
          lat
        }
      })
      .filter(Boolean)

    if (!dayPoints.length) continue

    const firstPoint = dayPoints[0]
    const map = new AMap.Map(containerId, {
      resizeEnable: true,
      zoom: 12,
      center: [firstPoint.lng, firstPoint.lat]
    })

    AMap.plugin(['AMap.Scale', 'AMap.ToolBar'], () => {
      map.addControl(new AMap.Scale())
      map.addControl(new AMap.ToolBar())
    })

    const overlays: any[] = []
    const markerColors = ['#3B82F6', '#F59E0B', '#8B5CF6', '#EC4899', '#14B8A6', '#F97316', '#6366F1', '#10B981']

    dayPoints.forEach((point: any, pointIndex: number) => {
      const marker = new AMap.Marker({
        position: [point.lng, point.lat],
        title: point.name,
        content: `<div style="background:${markerColors[pointIndex % markerColors.length]};color:#fff;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;font-size:12px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.18)">${pointIndex + 1}</div>`,
        offset: new AMap.Pixel(-12, -12),
        zIndex: 100 - pointIndex
      })
      marker.on('click', () => {
        new AMap.InfoWindow({
          content: `<div style="padding:8px;max-width:220px"><strong>${pointIndex + 1}. ${point.name}</strong><br/><span style="color:#909399;font-size:12px">${point.address || ''}</span></div>`,
          offset: new AMap.Pixel(0, -30)
        }).open(map, marker.getPosition())
      })
      overlays.push(marker)
      map.add(marker)
    })

    for (let i = 0; i < dayPoints.length - 1; i++) {
      const routePath = await getRealRoutePath(
        [dayPoints[i].lng, dayPoints[i].lat],
        [dayPoints[i + 1].lng, dayPoints[i + 1].lat]
      )

      const polyline = new AMap.Polyline({
        path: routePath.length >= 2 ? routePath : [[dayPoints[i].lng, dayPoints[i].lat], [dayPoints[i + 1].lng, dayPoints[i + 1].lat]],
        strokeColor: '#7EA4C8',
        strokeWeight: 4,
        strokeOpacity: 0.9,
        strokeStyle: routePath.length >= 2 ? 'solid' : 'dashed',
        lineJoin: 'round',
        lineCap: 'round',
        showDir: true,
        dirColor: '#7EA4C8',
        zIndex: 50
      })
      overlays.push(polyline)
      map.add(polyline)
    }

    map.setFitView(overlays)
    tripDayMaps.value.push(map)
  }
}

async function getRealRoutePath(
  from: [number, number],
  to: [number, number],
  mode?: string
): Promise<[number, number][]> {
  const normalizedMode = mode === 'walking' || mode === 'driving' || mode === 'transit' ? mode : undefined

  if (normalizedMode === 'walking') {
    const walkingPath = await searchRouteWithService('walking', from, to)
    if (walkingPath.length >= 2) return walkingPath
    const drivingFallback = await searchRouteWithService('driving', from, to)
    if (drivingFallback.length >= 2) return drivingFallback
    return []
  }

  if (normalizedMode === 'driving') {
    const drivingPath = await searchRouteWithService('driving', from, to)
    if (drivingPath.length >= 2) return drivingPath
    const walkingFallback = await searchRouteWithService('walking', from, to)
    if (walkingFallback.length >= 2) return walkingFallback
    return []
  }

  if (normalizedMode === 'transit') {
    const transitWalkingPath = await searchRouteWithService('walking', from, to)
    if (transitWalkingPath.length >= 2) return transitWalkingPath
    const transitDrivingFallback = await searchRouteWithService('driving', from, to)
    if (transitDrivingFallback.length >= 2) return transitDrivingFallback
    return []
  }

  const walkingPath = await searchRouteWithService('walking', from, to)
  if (walkingPath.length >= 2) return walkingPath

  const drivingPath = await searchRouteWithService('driving', from, to)
  if (drivingPath.length >= 2) return drivingPath

  return []
}

function parsePolylinePath(polyline: string): [number, number][] {
  if (!polyline?.trim()) return []

  try {
    return polyline
      .replace(/\|/g, ';')
      .split(';')
      .map((p: string) => p.trim())
      .filter((p: string) => p.includes(','))
      .map((p: string) => {
        const [lngStr, latStr] = p.split(',')
        return [Number(lngStr), Number(latStr)] as [number, number]
      })
      .filter(([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat) && !(lng === 0 && lat === 0))
  } catch {
    return []
  }
}

function buildFallbackSegmentPath(seg: any, idx: number): [number, number][] {
  if (seg?.from_location && seg?.to_location) {
    const fl = seg.from_location
    const tl = seg.to_location
    if (fl.longitude && fl.latitude && tl.longitude && tl.latitude) {
      return [[fl.longitude, fl.latitude], [tl.longitude, tl.latitude]]
    }
  }

  if (tripStore.orderedPois[idx] && tripStore.orderedPois[idx + 1]) {
    const a = tripStore.orderedPois[idx].location
    const b = tripStore.orderedPois[idx + 1].location
    if (a && b) {
      const alng = a.longitude || a.lng
      const alat = a.latitude || a.lat
      const blng = b.longitude || b.lng
      const blat = b.latitude || b.lat
      if (alng && alat && blng && blat) {
        return [[alng, alat], [blng, blat]]
      }
    }
  }

  return []
}

function searchRouteWithService(
  mode: 'walking' | 'driving',
  from: [number, number],
  to: [number, number]
): Promise<[number, number][]> {
  const AMap = (window as any).AMap
  if (!AMap) return Promise.resolve([])

  return new Promise((resolve) => {
    const ServiceCtor = mode === 'walking' ? AMap.Walking : AMap.Driving
    if (!ServiceCtor) {
      resolve([])
      return
    }

    const service = new ServiceCtor({ hideMarkers: true, autoFitView: false })
    service.search(from, to, (status: string, result: any) => {
      if (status !== 'complete') {
        resolve([])
        return
      }

      const route = result?.routes?.[0]
      const steps = route?.steps
      if (!steps?.length) {
        resolve([])
        return
      }

      const path: [number, number][] = []
      steps.forEach((step: any) => {
        const rawPath = Array.isArray(step.path)
          ? step.path
          : Array.isArray(step.polyline)
            ? step.polyline
            : []

        rawPath.forEach((point: any) => {
          const lng = typeof point?.lng === 'number' ? point.lng : Number(point?.getLng?.())
          const lat = typeof point?.lat === 'number' ? point.lat : Number(point?.getLat?.())
          if (Number.isFinite(lng) && Number.isFinite(lat)) {
            const prev = path[path.length - 1]
            if (!prev || prev[0] !== lng || prev[1] !== lat) {
              path.push([lng, lat])
            }
          }
        })
      })

      resolve(path)
    })
  })
}

async function createMap() {
  const AMap = (window as any).AMap
  if (!AMap) return

  const city = cityName.value
  const geocoder = new AMap.Geocoder()

  geocoder.getLocation(city, async (status: string, result: any) => {
    let cityCenter = [116.397428, 39.90923]
    if (status === 'complete' && result.geocodes?.length > 0) {
      cityCenter = [result.geocodes[0].location.lng, result.geocodes[0].location.lat]
    }

    const map = new AMap.Map('map-container', { resizeEnable: true, zoom: 12, center: cityCenter })
    AMap.plugin(['AMap.Scale', 'AMap.ToolBar'], () => {
      map.addControl(new AMap.Scale())
      map.addControl(new AMap.ToolBar())
    })
    mapInstance.value = map

    const markers: any[] = []
    let attractions: any[] = []

    if (tripStore.isLocalRoute && tripStore.orderedPois.length > 0) {
      attractions = tripStore.orderedPois
    } else if (tripPlan.value?.days) {
      for (const day of tripPlan.value.days) {
        if (day.attractions) attractions.push(...day.attractions)
      }
    }

    const tripData = tripPlan.value as any
    if (tripData?.start_location) {
      const sl = tripData.start_location
      const startMarker = new AMap.Marker({
        position: [sl.longitude, sl.latitude],
        title: tripData.start_name || '出发地点',
        content: '<div style="background:#303133;color:#fff;width:28px;height:28px;line-height:28px;text-align:center;border-radius:50%;font-size:14px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3)">🚩</div>',
        offset: new AMap.Pixel(-14, -14),
        zIndex: 200
      })
      startMarker.on('click', () => {
        new AMap.InfoWindow({
          content: `<div style="padding:8px"><strong>🚩 ${tripData.start_name || '出发地点'}</strong></div>`,
          offset: new AMap.Pixel(0, -30)
        }).open(map, startMarker.getPosition())
      })
      markers.push(startMarker)
      map.add(startMarker)
    }

    const markerColors = ['#409EFF', '#E6A23C', '#8B5CF6', '#F43F5E', '#06B6D4', '#10B981', '#F97316', '#EC4899', '#6366F1', '#14B8A6']

    attractions.forEach((attr: any, i: number) => {
      const loc = attr.location
      if (!loc) return
      const lng = loc.longitude || loc.lng
      const lat = loc.latitude || loc.lat
      if (!lng || !lat || (lng === 0 && lat === 0)) return

      const bgColor = markerColors[i % markerColors.length]
      const marker = new AMap.Marker({
        position: [lng, lat],
        title: attr.name,
        content: `<div style="background:${bgColor};color:#fff;width:24px;height:24px;line-height:24px;text-align:center;border-radius:50%;font-size:12px;font-weight:bold;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.3)">${i + 1}</div>`,
        offset: new AMap.Pixel(-12, -12),
        zIndex: 100 - i
      })
      marker.on('click', () => {
        new AMap.InfoWindow({
          content: `<div style="padding:8px;max-width:220px"><strong>${i + 1}. ${attr.name}</strong><br/><span style="color:#909399;font-size:12px">${attr.address || ''}</span></div>`,
          offset: new AMap.Pixel(0, -30)
        }).open(map, marker.getPosition())
      })
      markers.push(marker)
      map.add(marker)
    })

    const segs = tripStore.routeSegments
    const polylines: any[] = []

    if (tripStore.isLocalRoute && attractions.length > 1) {
      const orderedPoints = attractions
        .map((attr: any) => {
          const loc = attr.location
          if (!loc) return null
          const lng = loc.longitude || loc.lng
          const lat = loc.latitude || loc.lat
          if (!lng || !lat || (lng === 0 && lat === 0)) return null
          return { lng, lat }
        })
        .filter(Boolean)

      for (let i = 0; i < orderedPoints.length - 1; i++) {
        const seg = segs[i]
        const routePath = await getRealRoutePath(
          [orderedPoints[i].lng, orderedPoints[i].lat],
          [orderedPoints[i + 1].lng, orderedPoints[i + 1].lat],
          seg?.transport_mode
        )
        const fallbackPath = [[orderedPoints[i].lng, orderedPoints[i].lat], [orderedPoints[i + 1].lng, orderedPoints[i + 1].lat]] as [number, number][]
        const path = routePath.length >= 2 ? routePath : parsePolylinePath(seg?.polyline || '')
        const finalPath = path.length >= 2 ? path : fallbackPath

        const color = seg?.transport_mode === 'driving' ? '#409EFF'
                    : seg?.transport_mode === 'transit' ? '#E6A23C'
                    : '#8B5CF6'
        const polyline = new AMap.Polyline({
          path: finalPath,
          strokeColor: color,
          strokeWeight: 5,
          strokeOpacity: 0.9,
          showDir: true,
          dirColor: color,
          lineJoin: 'round',
          lineCap: 'round',
          strokeStyle: routePath.length >= 2 || path.length >= 2 ? 'solid' : 'dashed',
          zIndex: 60
        })
        polylines.push(polyline)
        map.add(polyline)
      }
    } else if (!tripStore.isLocalRoute && attractions.length > 1) {
      const orderedPoints: [number, number][] = []

      if (tripData?.start_location?.longitude && tripData?.start_location?.latitude) {
        orderedPoints.push([tripData.start_location.longitude, tripData.start_location.latitude])
      }

      attractions.forEach((attr: any) => {
        const loc = attr.location
        if (!loc) return
        const lng = loc.longitude || loc.lng
        const lat = loc.latitude || loc.lat
        if (lng && lat) {
          orderedPoints.push([lng, lat])
        }
      })

      for (let i = 0; i < orderedPoints.length - 1; i++) {
        const routePath = await getRealRoutePath(orderedPoints[i], orderedPoints[i + 1])
        const polyline = new AMap.Polyline({
          path: routePath.length >= 2 ? routePath : [orderedPoints[i], orderedPoints[i + 1]],
          strokeColor: '#7EA4C8',
          strokeWeight: 4,
          strokeOpacity: 0.88,
          strokeStyle: routePath.length >= 2 ? 'solid' : 'dashed',
          lineJoin: 'round',
          lineCap: 'round',
          showDir: true,
          dirColor: '#7EA4C8',
          zIndex: 50
        })
        polylines.push(polyline)
        map.add(polyline)
      }
    }


    if (markers.length > 0 || polylines.length > 0) {
      map.setFitView([...markers, ...polylines])
    }
  })
}


const handleDayCollapseChange = () => {
  if (!tripStore.isLocalRoute) {
    setTimeout(() => initMap(), 120)
  }
}

async function handleExportPDF() {
  ElMessage.info('正在生成PDF...')
  try {
    const html2canvas = (await import('html2canvas')).default
    const { jsPDF } = await import('jspdf')
    const element = document.querySelector('.content') as HTMLElement
    if (!element) return
    const canvas = await html2canvas(element, { scale: 2, useCORS: true, logging: false })
    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF('p', 'mm', 'a4')
    pdf.addImage(imgData, 'PNG', 0, 0, 210, (canvas.height * 210) / canvas.width)
    pdf.save(`${cityName.value}路线规划.pdf`)
    ElMessage.success('PDF导出成功')
  } catch (error) {
    ElMessage.error('PDF导出失败')
  }
}

function handleReset() {
  tripStore.reset()
  router.push('/')
}

async function handleApprove() {
  if (!tripStore.sessionId) return
  try {
    await approveTripPlan(tripStore.sessionId, reviewComment.value || 'approve')
    ElMessage.success('行程已确认！')
    showReviewDialog.value = false
  } catch { ElMessage.error('确认失败') }
}

async function handleReject() {
  if (!tripStore.sessionId) return
  try {
    await rejectTripPlan(tripStore.sessionId, reviewComment.value || 'reject')
    ElMessage.info('正在重新规划...')
    showReviewDialog.value = false
    router.push('/')
  } catch { ElMessage.error('操作失败') }
}

onMounted(() => {
  if (hasData.value) setTimeout(() => initMap(), 300)
})
</script>

<style scoped>
.result-container {
  min-height: 100vh;
  padding: 28px;
}

.header,
.content,
.empty-state {
  max-width: 1040px;
  margin-left: auto;
  margin-right: auto;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 24px;
  padding: 22px 26px;
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(18, 40, 72, 0.95), rgba(30, 58, 102, 0.94) 52%, rgba(89, 106, 188, 0.88));
  box-shadow: var(--ra-shadow-lg);
  color: #fff;
}

.header :deep(.el-button--text) {
  color: rgba(244, 247, 252, 0.94);
}

.header :deep(.el-button--default) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.14);
  color: #fff;
}

.header-title-block {
  flex: 1;
  min-width: 0;
}

.header h1 {
  margin: 0;
  font-size: clamp(28px, 4vw, 36px);
  line-height: 1.1;
  color: #fff;
}

.session-note {
  margin-top: 8px;
  color: rgba(229, 235, 245, 0.78);
  font-size: 13px;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.content {
  display: grid;
  gap: 20px;
}

.empty-state {
  margin-top: 100px;
}

.overview-card,
.map-card,
.metrics-card,
.route-overview-card,
.meals-card,
.tips-card,
.itinerary-card,
.budget-card {
  margin-bottom: 0;
}

:deep(.el-card__header) {
  padding: 18px 22px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

:deep(.el-card__body) {
  padding: 22px;
}

.card-header {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--ra-text);
  font-weight: 700;
}

:deep(.el-descriptions) {
  border-radius: 18px;
  overflow: hidden;
}

:deep(.el-descriptions__body .el-descriptions__table) {
  border-color: rgba(15, 23, 42, 0.06);
}

:deep(.el-descriptions__label.el-descriptions__cell.is-bordered-label) {
  color: var(--ra-text-soft);
  background: rgba(24, 59, 107, 0.04);
}

:deep(.el-descriptions__content.el-descriptions__cell.is-bordered-content) {
  color: var(--ra-text);
  background: rgba(255, 255, 255, 0.84);
}

.map-container {
  width: 100%;
  height: 420px;
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

.metrics-subtle {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 14px 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(15, 23, 42, 0.06);
  color: var(--ra-text-faint);
  font-size: 13px;
}

.metrics-subtle .metrics-label {
  margin-right: 6px;
  color: var(--ra-text-soft);
  font-weight: 700;
}

.metrics-subtle .metrics-main {
  font-size: 24px;
  font-weight: 700;
  color: var(--ra-primary);
}

.route-start-point {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(24, 59, 107, 0.06);
  color: var(--ra-text);
  font-weight: 600;
}

.route-timeline h4,
.dining-section h4,
.accommodation-section h4 {
  margin-bottom: 14px;
  color: var(--ra-text);
  font-size: 17px;
}

.route-poi-item {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.route-poi-item .poi-name {
  font-weight: 700;
  font-size: 15px;
  color: var(--ra-text);
}

.route-poi-item .route-info {
  font-size: 12px;
  color: var(--ra-text-faint);
}

.poi-detail {
  margin-top: 8px;
  font-size: 13px;
  color: var(--ra-text-soft);
  line-height: 1.7;
}

.day-map-block {
  margin: 8px 0 20px;
  padding: 16px;
  border-radius: 22px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(244, 247, 251, 0.88));
}

.day-map-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: var(--ra-text-soft);
  font-size: 13px;
  font-weight: 600;
}

.day-map-container {
  height: 340px;
}

.day-title {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  flex-wrap: wrap;
}

.day-date {
  color: var(--ra-text-faint);
  font-size: 13px;
}

.day-theme {
  color: var(--ra-text-soft);
}

.spot-card {
  margin-bottom: 8px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
}

.spot-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.spot-header h4 {
  margin: 0;
  color: var(--ra-text);
}

.spot-info p {
  color: var(--ra-text-soft);
  margin: 4px 0;
  line-height: 1.8;
}

.spot-details {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin: 10px 0;
  font-size: 13px;
  color: var(--ra-text-faint);
}

.spot-address,
.hotel-address {
  font-size: 13px;
  color: var(--ra-text-faint);
  margin-top: 4px;
}

.meal-card {
  height: 100%;
  text-align: left;
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(247, 248, 251, 0.9));
}

.meal-type {
  color: var(--ra-accent);
  font-weight: 700;
  margin-bottom: 8px;
  letter-spacing: 0.04em;
}

.meal-name,
.hotel-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--ra-text);
}

.meal-desc {
  margin: 8px 0;
  font-size: 13px;
  color: var(--ra-text-soft);
  line-height: 1.7;
}

.meal-price {
  font-weight: 700;
  color: var(--ra-primary);
}

.accommodation-section {
  margin-top: 20px;
}

.hotel-details {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin: 10px 0;
  color: var(--ra-text-soft);
}

.tips-text {
  color: var(--ra-text-soft);
  line-height: 1.9;
}

.tips-tags {
  margin-top: 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.total-budget {
  color: var(--ra-primary);
}

.review-content {
  padding: 10px 0 0;
}

.review-actions {
  margin-top: 18px;
}

:deep(.el-collapse) {
  border: none;
}

:deep(.el-collapse-item) {
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.76);
  overflow: hidden;
}

:deep(.el-collapse-item + .el-collapse-item) {
  margin-top: 14px;
}

:deep(.el-collapse-item__header) {
  min-height: 66px;
  padding: 0 18px;
  background: transparent;
  color: var(--ra-text);
  border-bottom: none;
}

:deep(.el-collapse-item__wrap) {
  background: transparent;
  border-bottom: none;
}

:deep(.el-collapse-item__content) {
  padding: 0 18px 18px;
}

:deep(.el-timeline-item__node--primary) {
  background: var(--ra-primary);
}

:deep(.el-timeline-item__node--success) {
  background: rgba(30, 143, 102, 0.18);
  border-color: rgba(30, 143, 102, 0.32);
}

:deep(.budget-card .el-statistic) {
  padding: 14px 12px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.68);
}

:deep(.budget-card .el-statistic__head) {
  color: var(--ra-text-soft);
}

:deep(.budget-card .el-statistic__content) {
  color: var(--ra-text);
}

@media (max-width: 1024px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .result-container {
    padding: 14px;
  }

  .header {
    padding: 20px;
    border-radius: 24px;
  }

  .map-container {
    height: 300px;
  }

  .metrics-subtle {
    align-items: flex-start;
  }
}
</style>
