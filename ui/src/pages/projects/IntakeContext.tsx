import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { api } from '@/lib/api'
import type {
  CitySummary,
  IntakeAnswers,
  ProjectType,
  ResolvedManifest,
} from '@/lib/types'

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
  const [step, setStep] = useState(1)

  // City data
  const [cities, setCities] = useState<CitySummary[]>([])
  const [citiesLoading, setCitiesLoading] = useState(true)
  const [cityOverlay, setCityOverlay] = useState<{ neighbourhoods?: string[] } | null>(null)

  // Form state
  const [municipality, setMunicipality] = useState('')
  const [projectType, setProjectType] = useState<ProjectType | null>(null)
  const [projectName, setProjectName] = useState('')
  const [developerName, setDeveloperName] = useState('')
  const [neighbourhood, setNeighbourhood] = useState('')
  const [constructionCost, setConstructionCost] = useState('')
  const [unitCount, setUnitCount] = useState('')
  const [floorArea, setFloorArea] = useState('')
  const [communityEngagement, setCommunityEngagement] = useState(false)
  const [indigenousEngagement, setIndigenousEngagement] = useState(false)
  const [requiresRezoning, setRequiresRezoning] = useState(false)
  const [civicContribution, setCivicContribution] = useState(true)

  // Preview state
  const [preview, setPreview] = useState<ResolvedManifest | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Submit state
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

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
    requires_rezoning: requiresRezoning,
    community_engagement: communityEngagement,
    indigenous_engagement: indigenousEngagement,
    conditions: {
      civic_contribution: civicContribution,
    },
  }), [
    municipality, projectType, projectName, developerName, neighbourhood,
    constructionCost, unitCount, floorArea, requiresRezoning,
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
    constructionCost, unitCount, floorArea,
    communityEngagement, indigenousEngagement, requiresRezoning, civicContribution,
    cities, citiesLoading, selectedCity, cityOverlay,
    preview, previewLoading, submitting, submitError,
    handleSubmit, buildIntake, step, canAdvance,
  ])

  return <IntakeCtx.Provider value={value}>{children}</IntakeCtx.Provider>
}
