import { useState, useEffect, useMemo, useCallback } from 'react'
import { Play, Send } from 'lucide-react'
import { Badge } from '@ui/atoms'
import { ModuleLayout } from '@/components/ModuleLayout'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { WiringManifest, diagnoseProvider } from '@/components/integrations'
import { useIntegrationStatus } from '@/hooks/useIntegrationStatus'
import { useOAuthConnect } from '@/hooks/useOAuthConnect'
import { api } from '@/lib/api'

import { FilterBar } from './components/FilterBar'
import { PreambleSection } from './components/PreambleSection'
import { ProjectRow } from './components/ProjectRow'
import type { BfaTodoStatus, BfaTodoProject, BfaTodoPreamble, SourceType, TargetType } from './types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function matchesSearch(p: BfaTodoProject, q: string): boolean {
  const lower = q.toLowerCase()
  return (
    p.client.toLowerCase().includes(lower) ||
    p.project_name.toLowerCase().includes(lower) ||
    p.city.toLowerCase().includes(lower) ||
    p.phase.toLowerCase().includes(lower) ||
    p.owner_team.toLowerCase().includes(lower)
  )
}

function distinct<T>(arr: T[]): T[] {
  return Array.from(new Set(arr)).sort() as T[]
}


// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function BfaTodoPage() {
  const [status, setStatus] = useState<BfaTodoStatus | null>(null)
  const [projects, setProjects] = useState<BfaTodoProject[]>([])
  const [loading, setLoading] = useState(true)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [rendering, setRendering] = useState(false)
  const [deploying, setDeploying] = useState(false)
  const [docId, setDocId] = useState('')

  // Source/Target pipeline
  const [source, setSource] = useState<SourceType>('bfa-html')
  const [target, setTarget] = useState<TargetType>('none')
  const [excelPath, setExcelPath] = useState('')
  const [importingExcel, setImportingExcel] = useState(false)
  const [htmlPath, setHtmlPath] = useState('C:/Users/Neal/dev/BFA-todo/data')
  const [importingHtml, setImportingHtml] = useState(false)

  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [filterPhase, setFilterPhase] = useState('')
  const [filterLead, setFilterLead] = useState('')
  const [filterCity, setFilterCity] = useState('')
  const [showOnHold, setShowOnHold] = useState(false)
  const [showIssuesOnly, setShowIssuesOnly] = useState(false)

  // Selection & expansion
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  // Preamble
  const [preambles, setPreambles] = useState<BfaTodoPreamble[]>([])
  const [preambleExpanded, setPreambleExpanded] = useState<Set<string>>(new Set())


  // Integration status + GDocs
  const { status: integrations, refresh: refreshIntegrations } = useIntegrationStatus()
  const oauth = useOAuthConnect(refreshIntegrations)
  const [memberMap, setMemberMap] = useState<Record<string, string>>({})

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      api.bfaTodo.status().catch(() => null),
      api.bfaTodo.projects().catch(() => []),
      api.bfaTodo.preambles().catch(() => []),
    ]).then(([s, p, pre]) => {
      if (s) setStatus(s)
      setProjects(p)
      setPreambles(pre)
      setLoading(false)
    })
  }, [])

  useEffect(load, [load])

  useEffect(() => {
    api.config.get().then(cfg => {
      if (cfg.bfa_todo_doc_id) setDocId(String(cfg.bfa_todo_doc_id))
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (integrations?.clickup.configured) {
      api.clickup.members().then(members => {
        const map: Record<string, string> = {}
        for (const m of members) {
          if (m.initials) map[m.initials] = m.username
        }
        setMemberMap(map)
      }).catch(() => {})
    }
  }, [integrations?.clickup.configured])

  // Derived filter options
  const phases = useMemo(() => distinct(projects.map(p => p.phase).filter(Boolean)), [projects])
  const leads = useMemo(() => distinct(projects.map(p => p.owner_team).filter(Boolean)), [projects])
  const cities = useMemo(() => distinct(projects.map(p => p.city).filter(Boolean)), [projects])
  const onHoldCount = useMemo(() => projects.filter(p => p.status === 'on_hold').length, [projects])
  const issueCount = useMemo(() => projects.filter(p => p.validation && (p.validation.error_count > 0 || p.validation.warning_count > 0)).length, [projects])

  const filtered = useMemo(() => {
    return projects.filter(p => {
      if (!showOnHold && p.status === 'on_hold') return false
      if (showIssuesOnly && p.validation && p.validation.error_count === 0 && p.validation.warning_count === 0) return false
      if (searchQuery && !matchesSearch(p, searchQuery)) return false
      if (filterPhase && p.phase !== filterPhase) return false
      if (filterLead && p.owner_team !== filterLead) return false
      if (filterCity && p.city !== filterCity) return false
      return true
    })
  }, [projects, searchQuery, filterPhase, filterLead, filterCity, showOnHold, showIssuesOnly])

  // Toggle helpers
  const toggleExpanded = (uid: string) => {
    setExpanded(prev => { const next = new Set(prev); next.has(uid) ? next.delete(uid) : next.add(uid); return next })
  }
  const toggleSelected = (uid: string) => {
    setSelected(prev => { const next = new Set(prev); next.has(uid) ? next.delete(uid) : next.add(uid); return next })
  }
  const togglePreambleExpanded = (uid: string) => {
    setPreambleExpanded(prev => { const next = new Set(prev); next.has(uid) ? next.delete(uid) : next.add(uid); return next })
  }
  const toggleSelectAll = () => {
    selected.size === filtered.length ? setSelected(new Set()) : setSelected(new Set(filtered.map(p => p.uid)))
  }

  // Actions
  const handleRender = async () => {
    setRendering(true); setFeedback('')
    try {
      const result = await api.bfaTodo.render()
      if (result.error) { setFeedback(result.error); setFeedbackErr(true) }
      else { setFeedback(`Rendered ${result.project_count} projects`); setFeedbackErr(false); load() }
    } catch (e: any) { setFeedback(e.message ?? 'Render failed'); setFeedbackErr(true) }
    setRendering(false)
  }

  const handleDeploySelected = async () => {
    if (!docId.trim() || selected.size === 0) return
    setDeploying(true); setFeedback('')
    api.config.save({ bfa_todo_doc_id: docId.trim() }).catch(() => {})
    try {
      const result = await api.bfaTodo.deploySelected(docId.trim(), Array.from(selected))
      if (result.error) { setFeedback(result.error); setFeedbackErr(true) }
      else { setFeedback(`Deployed ${result.deployed} projects (${result.errors} errors)`); setFeedbackErr(result.errors > 0) }
    } catch (e: any) { setFeedback(e.message ?? 'Deploy failed'); setFeedbackErr(true) }
    setDeploying(false)
  }

  const handleImportExcel = async () => {
    if (!excelPath.trim()) return
    setImportingExcel(true); setFeedback('')
    try {
      const result = await api.bfaTodo.importExcel(excelPath.trim())
      if (result.error) { setFeedback(result.error); setFeedbackErr(true) }
      else { setFeedback(`Imported ${result.project_count ?? ''} projects from Excel`); setFeedbackErr(false); load() }
    } catch (e: any) { setFeedback(e.message ?? 'Excel import failed'); setFeedbackErr(true) }
    setImportingExcel(false)
  }

  const handleImportHtml = async () => {
    if (!htmlPath.trim()) return
    setImportingHtml(true); setFeedback('')
    try {
      const result = await api.bfaTodo.importHtml(htmlPath.trim())
      if (result.error) { setFeedback(result.error); setFeedbackErr(true) }
      else { setFeedback(`Imported ${result.project_count} projects from HTML source`); setFeedbackErr(false); load() }
    } catch (e: any) { setFeedback(e.message ?? 'HTML import failed'); setFeedbackErr(true) }
    setImportingHtml(false)
  }

  return (
    <ModuleLayout module="bfa-todo" activePage="overview">
      <div className="flex flex-col gap-3" style={{ height: 'calc(100vh - 48px)' }}>
        {loading ? (
          <p className="text-sm text-ws-text-secondary py-8 text-center">Loading...</p>
        ) : (
          <>
            <WiringManifest module="bfa-todo" status={integrations} />

            {/* Source endpoint */}
            <div className="endpoint-bar">
              <span className="endpoint-label">Source</span>
              <select className="endpoint-select" value={source} onChange={e => setSource(e.target.value as SourceType)}>
                <option value="bfa-html">BFA HTML</option>
                <option value="monday-excel">Monday Excel</option>
                <option value="clickup" disabled>ClickUp (coming soon)</option>
              </select>
              {source === 'bfa-html' && (
                <>
                  <input type="text" className="endpoint-input" value={htmlPath} onChange={e => setHtmlPath(e.target.value)} placeholder="Path to BFA HTML data directory..." onKeyDown={e => { if (e.key === 'Enter') handleImportHtml() }} />
                  <button className="btn btn-sm btn-primary" onClick={handleImportHtml} disabled={importingHtml || !htmlPath.trim()}>
                    {importingHtml ? 'Importing...' : 'Re-import'}
                  </button>
                </>
              )}
              {source === 'monday-excel' && (
                <>
                  <input type="text" className="endpoint-input" value={excelPath} onChange={e => setExcelPath(e.target.value)} placeholder="Path to Monday .xlsx export..." onKeyDown={e => { if (e.key === 'Enter') handleImportExcel() }} />
                  <button className="btn btn-sm btn-primary" onClick={handleImportExcel} disabled={importingExcel || !excelPath.trim()}>
                    {importingExcel ? 'Importing...' : 'Import'}
                  </button>
                </>
              )}
            </div>

            <FilterBar
              searchQuery={searchQuery} onSearchChange={setSearchQuery}
              filterPhase={filterPhase} onPhaseChange={setFilterPhase}
              filterLead={filterLead} onLeadChange={setFilterLead}
              filterCity={filterCity} onCityChange={setFilterCity}
              showOnHold={showOnHold} onShowOnHoldChange={setShowOnHold}
              showIssuesOnly={showIssuesOnly} onShowIssuesOnlyChange={setShowIssuesOnly}
              phases={phases} leads={leads} cities={cities}
              onHoldCount={onHoldCount} issueCount={issueCount}
              memberMap={memberMap}
            />

            {/* Status bar */}
            {status && (
              <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--fg-secondary)', fontFamily: 'var(--font-sans)' }}>
                <span>{status.project_count} projects total</span>
                {status.last_render && <span>Last render: {new Date(status.last_render).toLocaleString()}</span>}
                <div className="flex gap-1.5">
                  {status.has_html && <Badge variant="success" size="xs">HTML</Badge>}
                  {status.has_json && <Badge variant="success" size="xs">JSON</Badge>}
                  {status.has_gdocs && <Badge variant="success" size="xs">GDocs</Badge>}
                </div>
              </div>
            )}

            <PreambleSection
              preambles={preambles}
              preambleExpanded={preambleExpanded}
              onTogglePreambleExpanded={togglePreambleExpanded}
            />

            {/* Project list */}
            <div className="flex-1 overflow-y-auto" style={{ border: '1px solid var(--border)' }}>
              <div className="flex items-center gap-2 px-3 py-1.5" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)', fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)' }}>
                <input type="checkbox" checked={filtered.length > 0 && selected.size === filtered.length} onChange={toggleSelectAll} style={{ accentColor: 'var(--accent)' }} />
                <span style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  {filtered.length} projects{selected.size > 0 && ` · ${selected.size} selected`}
                </span>
              </div>

              {filtered.length === 0 ? (
                <p className="not-configured" style={{ padding: '24px', textAlign: 'center' }}>No projects match filters</p>
              ) : (
                filtered.map(p => (
                  <ProjectRow
                    key={p.uid}
                    project={p}
                    isExpanded={expanded.has(p.uid)}
                    isSelected={selected.has(p.uid)}
                    memberMap={memberMap}
                    onToggleExpand={() => toggleExpanded(p.uid)}
                    onToggleSelect={() => toggleSelected(p.uid)}
                    onProjectUpdated={load}
                  />
                ))
              )}
            </div>

            {/* Process + Target endpoint */}
            <div className="endpoint-bar">
              <button className="btn btn-sm" onClick={handleRender} disabled={rendering}>
                <Play size={12} />
                {rendering ? 'Rendering...' : 'Render All'}
              </button>

              <span className="endpoint-divider" />

              <span className="endpoint-label">Target</span>
              <select className="endpoint-select" value={target} onChange={e => setTarget(e.target.value as TargetType)}>
                <option value="none">None (local only)</option>
                <option value="google-docs">Google Docs</option>
                <option value="clickup" disabled>ClickUp (coming soon)</option>
              </select>

              {target === 'google-docs' && (() => {
                const diag = diagnoseProvider('google', integrations)
                return (
                  <>
                    <span className="endpoint-status">{diag.summary}</span>
                    {!diag.healthy && integrations?.google.oauth_available && (
                      <button className="btn btn-sm btn-primary" onClick={() => oauth.connect('Google', api.google.auth, 'google-oauth')}>
                        Connect
                      </button>
                    )}
                    {diag.healthy && (
                      <>
                        <input type="text" className="endpoint-input" value={docId} onChange={e => setDocId(e.target.value)} placeholder="Doc ID" style={{ width: '200px', borderColor: !docId.trim() ? 'var(--color-warning)' : undefined }} onKeyDown={e => { if (e.key === 'Enter') handleDeploySelected() }} />
                        <button className="btn btn-sm btn-primary" onClick={handleDeploySelected} disabled={deploying || !docId.trim() || selected.size === 0}>
                          <Send size={12} />
                          {deploying ? 'Deploying...' : `Deploy (${selected.size})`}
                        </button>
                      </>
                    )}
                  </>
                )
              })()}

              <FeedbackMessage message={feedback} isError={feedbackErr} />
            </div>
          </>
        )}
      </div>
    </ModuleLayout>
  )
}
