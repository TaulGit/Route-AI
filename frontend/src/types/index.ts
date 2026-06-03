// TypeScript 类型定义

// ============================================
// 基础类型
// ============================================

export interface Location {
  longitude: number
  latitude: number
}

export interface POI {
  id: string
  name: string
  address: string
  location: Location
  category?: string
  rating?: number
  tel?: string
  ticket_price?: number
  visit_duration?: number
  description?: string
  image_url?: string
  popularity_score?: number
  queue_time_min?: number
}

export interface Review {
  id: string
  poi_name: string
  user_name: string
  rating: number
  content: string
  date: string
  sentiment: 'positive' | 'neutral' | 'negative'
  tags: string[]
  like_count: number
}

export interface Weather {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number | string
  night_temp: number | string
  wind_direction: string
  wind_power: string
}

export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  type: string
  estimated_cost?: number
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner'
  name: string
  address?: string
  description?: string
  estimated_cost?: number
}

export interface Attraction {
  name: string
  address: string
  location: Location
  visit_duration: number
  description: string
  category?: string
  ticket_price?: number
}

export interface RouteSegment {
  from_poi: string
  to_poi: string
  from_location: Location
  to_location: Location
  distance_meters: number
  duration_minutes: number
  polyline: string
  transport_mode: 'driving' | 'walking' | 'transit'
  cost_estimate: number
}

export interface DayPlan {
  date: string
  day_index: number
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total: number
}

export interface OptimizationMetrics {
  time_efficiency: number
  cost_efficiency: number
  preference_match: number
  route_coherence: number
  overall_score: number
}

export interface RoutePlan {
  city: string
  date: string
  start_location?: Location
  start_time?: string
  ordered_pois: Attraction[]
  route_segments: RouteSegment[]
  total_distance_km: number
  total_duration_minutes: number
  total_cost: number
  optimization_metrics?: OptimizationMetrics
  meals: Meal[]
  weather?: Weather
  suggestions: string
  trade_off_explanations: string[]
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: Weather[]
  overall_suggestions: string
  budget?: Budget
}

export interface TripRequest {
  session_id?: string
  city: string
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  free_text_input?: string
  llm_provider?: string
  budget?: [number, number]
}

export interface LocalRouteRequest {
  session_id?: string
  user_id?: string
  city: string
  date: string
  start_location?: Location
  start_address?: string
  start_time?: string
  end_time?: string
  transportation: string
  preferences: string[]
  free_text_input?: string
  budget?: [number, number]
  llm_provider?: string
  poi_count: number
}

export interface TripPlanResponse {
  success: boolean
  message: string
  data?: TripPlan
  route_plan?: RoutePlan
  status: TripStatus
}

export type TripStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'need_confirm'

export interface AgentStep {
  node: string
  status: string
  message?: string
  input?: Record<string, unknown>
  output?: Record<string, unknown>
  duration_ms?: number
  error?: string
  data?: Record<string, unknown>
}

export interface StreamingResponse {
  session_id: string
  step: number
  node: string
  status: TripStatus
  message: string
  data?: Record<string, unknown>
  thought?: string
  steps: AgentStep[]
}

export interface ChatMessage {
  session_id: string
  message: string
  message_type?: string
  llm_provider?: string
}

export interface ChatResponse {
  session_id: string
  response: string
  trip_plan?: TripPlan
}

export interface UserFeedback {
  session_id: string
  action: 'approve' | 'modify' | 'reject'
  modifications?: Record<string, unknown>
  comment?: string
}

export interface LLMProvider {
  name: string
  model: string
}

export interface AuthUser {
  id: number
  username: string
  email: string
}

export interface LoginRequest {
  username_or_email: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export interface ChatHistoryItem {
  session_id: string
  title: string
  latest_message: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatHistoryDetail {
  session_id: string
  title: string
  history: Array<{
    role: 'user' | 'assistant'
    content: string
    timestamp?: string
  }>
}

export interface TripHistoryItem {
  session_id: string
  title: string
  city: string
  record_type: string
  created_at: string
  updated_at: string
}

export interface TripHistoryDetail {
  session_id: string
  title: string
  city: string
  record_type: string
  request_data: Record<string, unknown>
  result_data: TripPlan | RoutePlan | Record<string, unknown> | null
  created_at: string
  updated_at: string
}
