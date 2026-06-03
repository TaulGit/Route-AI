import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { TripPlan, RoutePlan, RouteSegment, OptimizationMetrics, AgentStep, TripStatus } from '@/types'

export const useTripStore = defineStore('trip', () => {
  const sessionId = ref<string>('')
  const title = ref<string>('')
  const tripPlan = ref<TripPlan | null>(null)

  const routePlan = ref<RoutePlan | null>(null)
  const routeSegments = ref<RouteSegment[]>([])
  const orderedPois = ref<any[]>([])
  const optimizationMetrics = ref<OptimizationMetrics | null>(null)
  const isLocalRoute = ref(false)

  const status = ref<TripStatus>('pending')
  const currentStep = ref<string>('')
  const steps = ref<AgentStep[]>([])
  const errors = ref<string[]>([])
  const needHumanReview = ref(false)

  const isProcessing = computed(() => status.value === 'processing')
  const isCompleted = computed(() => status.value === 'completed')
  const hasErrors = computed(() => errors.value.length > 0)

  function setSessionId(id: string) {
    sessionId.value = id
  }

  function setTitle(value: string) {
    title.value = value
  }

  function setTripPlan(plan: TripPlan | null) {
    tripPlan.value = plan
  }

  function setRoutePlan(plan: RoutePlan | null) {
    routePlan.value = plan
    if (plan) {
      isLocalRoute.value = true
      routeSegments.value = plan.route_segments || []
      orderedPois.value = plan.ordered_pois || []
      if (plan.optimization_metrics) {
        optimizationMetrics.value = plan.optimization_metrics
      }
    }
  }

  function setRouteSegments(segs: RouteSegment[]) {
    routeSegments.value = segs
  }

  function setOrderedPois(pois: any[]) {
    orderedPois.value = pois
  }

  function setOptimizationMetrics(metrics: OptimizationMetrics | null) {
    optimizationMetrics.value = metrics
  }

  function setStatus(newStatus: TripStatus) {
    status.value = newStatus
  }

  function setCurrentStep(step: string) {
    currentStep.value = step
  }

  function addStep(step: AgentStep) {
    steps.value.push(step)
  }

  function setSteps(newSteps: AgentStep[]) {
    steps.value = newSteps
  }

  function addError(error: string) {
    errors.value.push(error)
  }

  function setErrors(newErrors: string[]) {
    errors.value = newErrors
  }

  function setNeedHumanReview(need: boolean) {
    needHumanReview.value = need
  }

  function loadTripHistory(session: string, tripTitle: string, plan: any, recordType: string) {
    sessionId.value = session
    title.value = tripTitle
    if (recordType === 'local_route') {
      setTripPlan(plan)
      setRoutePlan(plan as RoutePlan)
    } else {
      routePlan.value = null
      routeSegments.value = []
      orderedPois.value = []
      optimizationMetrics.value = null
      isLocalRoute.value = false
      setTripPlan(plan as TripPlan)
    }
    status.value = 'completed'
  }

  function reset() {
    sessionId.value = ''
    title.value = ''
    tripPlan.value = null
    routePlan.value = null
    routeSegments.value = []
    orderedPois.value = []
    optimizationMetrics.value = null
    isLocalRoute.value = false
    status.value = 'pending'
    currentStep.value = ''
    steps.value = []
    errors.value = []
    needHumanReview.value = false
  }

  return {
    sessionId,
    title,
    tripPlan,
    routePlan,
    routeSegments,
    orderedPois,
    optimizationMetrics,
    isLocalRoute,
    status,
    currentStep,
    steps,
    errors,
    needHumanReview,
    isProcessing,
    isCompleted,
    hasErrors,
    setSessionId,
    setTitle,
    setTripPlan,
    setRoutePlan,
    setRouteSegments,
    setOrderedPois,
    setOptimizationMetrics,
    setStatus,
    setCurrentStep,
    addStep,
    setSteps,
    addError,
    setErrors,
    setNeedHumanReview,
    loadTripHistory,
    reset
  }
})
