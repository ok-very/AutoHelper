import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { api } from '@/lib/api'
import type {
  CitySummary,
  IntakeAnswers,
  ProjectType,
  ResolvedManifest,
} from '@/lib/types'

// ---------------------------------------------------------------------------
// Session persistence — survives browser back/forward, clears on submit/cancel
// ---------------------------------------------------------------------------

const SESSION_KEY = 'intake-wizard-draft'

interface DraftState {
  step: number
  municipality: string
  projectType: ProjectType | null
  projectName: string
  developerName: string
  neighbourhood: string
  constructionCost: string
  unitCount: string
  floorArea: string
  fsr: string
  communityEngagement: boolean
  indigenousEngagement: boolean
  requiresRezoning: boolean
  civicContribution: boolean
}

function loadDraft(): Partial<DraftState> {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function saveDraft(state: DraftState) {
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(state)) } catch {}
}

export function clearIntakeDraft() {
  try { sessionStorage.removeItem(SESSION_KEY) } catch {}
}

// ---------------------------------------------------------------------------
// Context value
// ---------------------------------------------------------------------------

interface IntakeContextValue {
  // Form state
  municipality: string
  setMunicipality: (v: string) => void
  projectType: ProjectType | null
  setProjectType: (v: ProjectType | null) => void
  projectName: string
  setProjectName: (v: string) => void
  developerName: string
  setDeveloperName: (v: string) => void
  neighbourhood: string
  setNeighbourhood: (v: string) => void
  constructionCost: string
  setConstructionCost: (v: string) => void
  unitCount: string
  setUnitCount: (v: string) => void
  floorArea: string
  setFloorArea: (v: string) => void
  fsr: string
  setFsr: (v: string) => void
  communityEngagement: boolean
  setCommunityEngagement: (v: boolean) => void
  indigenousEngagement: boolean
  setIndigenousEngagement: (v: boolean) => void
  requiresRezoning: boolean
  setRequiresRezoning: (v: boolean) => void
  civicContribution: boolean
  setCivicContribution: (v: boolean) => void

  // City data
  cities: CitySummary[]
  citiesLoading: boolean
  selectedCity: CitySummary | null
  cityOverlay: { neighbourhoods?: string[] } | null

  // Preview
  preview: ResolvedManifest | null
  previewLoading: boolean

  // Submit
  submitting: boolean
  submitError: string | null
  handleSubmit: (provision: boolean) => Promise<void>

  // Derived
  buildIntake: () => IntakeAnswers

  // Step
  step: number
  setStep: (s: number) => void
  canAdvance: boolean
}

const IntakeCtx = createContext<IntakeContextValue | null>(null)

export function useIntake(): IntakeContextValue {
  const ctx = useContext(IntakeCtx)
  if (!ctx) throw new Error('useIntake must be used within IntakeContextProvider')
  return ctx
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function IntakeContextProvider({ children }: { children: React.ReactNode }) {
  const draft = useRef(loadDraft()).current

  const [step, setStep] = useState(draft.step ?? 1)

  // City data
  const [cities, setCities] = useState<CitySummary[]>([])
  const [citiesLoading, setCitiesLoading] = useState(true)
  const [cityOverlay, setCityOverlay] = useState<{ neighbourhoods?: string[] } | null>(null)

  // Form state — initialized from session draft
  const [municipality, setMunicipality] = useState(draft.municipality ?? '')
  const [projectType, setProjectType] = useState<ProjectType | null>(draft.projectType ?? null)
  const [projectName, setProjectName] = useState(draft.projectName ?? '')
  const [developerName, setDeveloperName] = useState(draft.developerName ?? '')
  const [neighbourhood, setNeighbourhood] = useState(draft.neighbourhood ?? '')
  const [constructionCost, setConstructionCost] = useState(draft.constructionCost ?? '')
  const [unitCount, setUnitCount] = useState(draft.unitCount ?? '')
  const [floorArea, setFloorArea] = useState(draft.floorArea ?? '')
  const [fsr, setFsr] = useState(draft.fsr ?? '')
  const [communityEngagement, setCommunityEngagement] = useState(draft.communityEngagement ?? false)
  const [indigenousEngagement, setIndigenousEngagement] = useState(draft.indigenousEngagement ?? false)
  const [requiresRezoning, setRequiresRezoning] = useState(draft.requiresRezoning ?? false)
  const [civicContribution, setCivicContribution] = useState(draft.civicContribution ?? true)

  // Preview state
  const [preview, setPreview] = useState<ResolvedManifest | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Submit state
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Persist to session on every form change
  useEffect(() => {
    saveDraft({
      step, municipality, projectType, projectName, developerName, neighbourhood,
      constructionCost, unitCount, floorArea, fsr,
      communityEngagement, indigenousEngagement, requiresRezoning, civicContribution,
    })
  }, [
    step, municipality, projectType, projectName, developerName, neighbourhood,
    constructionCost, unitCount, floorArea, fsr,
    communityEngagement, indigenousEngagement, requiresRezoning, civicContribution,
  ])

  // Derived
  const selectedCity = useMemo(
    () => cities.find((c) => c.city_id === municipality) ?? null,
    [cities, municipality]
  )

  // Load cities on mount
  useEffect(() => {
    api.projects.cities()
      .then(setCities)
      .catch(() => {})
      .finally(() => setCitiesLoading(false))
  }, [])

  // Load city overlay when municipality changes
  useEffect(() => {
    if (!municipality) {
      setCityOverlay(null)
      return
    }
    api.projects.city(municipality)
      .then((data: any) => {
        setCityOverlay({
          neighbourhoods: data.thresholds?.neighbourhoods ?? data.neighbourhoods ?? [],
        })
      })
      .catch(() => setCityOverlay(null))
  }, [municipality])

  // Build intake object
  const buildIntake = useCallback((): IntakeAnswers => ({
    municipality,
    project_type: projectType ?? 'private_development',
    project_name: projectName,
    developer_name: developerName || null,
    neighbourhood: neighbourhood || null,
    construction_cost: parseFloat(constructionCost) || 0,
    unit_count: unitCount ? parseInt(unitCount, 10) : null,
    floor_area_sqm: floorArea ? parseFloat(floorArea) : null,
    fsr: fsr ? parseFloat(fsr) : null,
    requires_rezoning: requiresRezoning,
    community_engagement: communityEngagement,
    indigenous_engagement: indigenousEngagement,
    conditions: {
      civic_contribution: civicContribution,
    },
  }), [
    municipality, projectType, projectName, developerName, neighbourhood,
    constructionCost, unitCount, floorArea, fsr, requiresRezoning,
    communityEngagement, indigenousEngagement, civicContribution,
  ])

  // Debounced preview on step 3 and 5
  useEffect(() => {
    if (step !== 3 && step !== 5) return
    if (!municipality || !projectType) return

    if (previewTimer.current) clearTimeout(previewTimer.current)
    previewTimer.current = setTimeout(() => {
      setPreviewLoading(true)
      api.projects.preview(buildIntake())
        .then((data: ResolvedManifest) => setPreview(data))
        .catch(() => setPreview(null))
        .finally(() => setPreviewLoading(false))
    }, step === 5 ? 100 : 500)

    return () => {
      if (previewTimer.current) clearTimeout(previewTimer.current)
    }
  }, [step, buildIntake, municipality, projectType])

  // Navigation validation
  const canAdvance = useMemo(() => {
    switch (step) {
      case 1: return !!municipality && !!projectType
      case 2: return !!projectName.trim()
      case 3: return parseFloat(constructionCost) > 0
      case 4: return true
      case 5: return true
      default: return false
    }
  }, [step, municipality, projectType, projectName, constructionCost])

  // Submit
  const handleSubmit = useCallback(async (provision: boolean) => {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const intake = buildIntake()
      const created = await api.projects.create(intake)
      if (provision && created.id) {
        await api.projects.provision(created.id)
      }
      clearIntakeDraft()
      window.location.href = `/projects/${created.id}`
    } catch (err: any) {
      setSubmitError(err.message ?? 'Failed to create project')
      setSubmitting(false)
    }
  }, [buildIntake])

  const value = useMemo<IntakeContextValue>(() => ({
    municipality, setMunicipality: (v: string) => { setMunicipality(v); setNeighbourhood('') },
    projectType, setProjectType,
    projectName, setProjectName,
    developerName, setDeveloperName,
    neighbourhood, setNeighbourhood,
    constructionCost, setConstructionCost,
    unitCount, setUnitCount,
    floorArea, setFloorArea,
    fsr, setFsr,
    communityEngagement, setCommunityEngagement,
    indigenousEngagement, setIndigenousEngagement,
    requiresRezoning, setRequiresRezoning,
    civicContribution, setCivicContribution,
    cities, citiesLoading, selectedCity, cityOverlay,
    preview, previewLoading,
    submitting, submitError, handleSubmit,
    buildIntake,
    step, setStep, canAdvance,
  }), [
    municipality, projectType, projectName, developerName, neighbourhood,
    constructionCost, unitCount, floorArea, fsr,
    communityEngagement, indigenousEngagement, requiresRezoning, civicContribution,
    cities, citiesLoading, selectedCity, cityOverlay,
    preview, previewLoading, submitting, submitError,
    handleSubmit, buildIntake, step, canAdvance,
  ])

  return <IntakeCtx.Provider value={value}>{children}</IntakeCtx.Provider>
}
