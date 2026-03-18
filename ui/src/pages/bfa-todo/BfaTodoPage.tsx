import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { clsx } from 'clsx'
import { ChevronRight, Search, Play, Send, Upload, X, Save, AlertTriangle, Check, Pencil } from 'lucide-react'
import { Badge } from '@ui/atoms'
import { ModuleLayout } from '@/components/ModuleLayout'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'
import type { IntegrationStatus } from '@/lib/api'

// ---------------------------------------------------------------------------
// Source/Target types
// ---------------------------------------------------------------------------

type SourceType = 'bfa-html' | 'monday-excel' | 'clickup'
type TargetType = 'none' | 'google-docs' | 'clickup'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BfaTodoStatus {
  project_count: number
  last_render: string | null
  has_html: boolean
  has_json: boolean
  has_gdocs: boolean
}

interface ValidationItem {
  field: string
  level: 'error' | 'warning'
  code: string
  message: string
  suggestion: string | null
}

interface Validation {
  error_count: number
  warning_count: number
  items: ValidationItem[]
}

interface BfaTodoProject {
  uid: string
  slug: string
  client: string
  project_name: string
  city: string
  phase: string
  owner_team: string
  status: 'active' | 'on_hold'
  validation: Validation
}

interface BfaTodoPreamble {
  uid: string
  slug: string
  type: 'preamble' | 'preamble-lists'
  title: string
}

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

/** Open an OAuth popup and return a promise that resolves on postMessage success. */
function openOAuthPopup(
  fetchAuth: () => Promise<{ url: string }>,
  messageType: string,
): Promise<boolean> {
  return new Promise(async (resolve) => {
    try {
      const { url } = await fetchAuth()
      const popup = window.open(url, `${messageType}-popup`, 'width=600,height=700,popup=yes')
      const handler = (e: MessageEvent) => {
        if (e.data?.type === messageType) {
          window.removeEventListener('message', handler)
          resolve(e.data.ok === true)
        }
      }
      window.addEventListener('message', handler)
      const timer = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(timer)
          window.removeEventListener('message', handler)
          setTimeout(() => resolve(false), 300)
        }
      }, 500)
    } catch {
      resolve(false)
    }
  })
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
  const [integrations, setIntegrations] = useState<IntegrationStatus | null>(null)
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

  // Load integration status + saved doc ID on mount
  useEffect(() => {
    api.integrations.status().then(setIntegrations).catch(() => {})
    api.config.get().then(cfg => {
      if (cfg.bfa_todo_doc_id) setDocId(String(cfg.bfa_todo_doc_id))
    }).catch(() => {})
  }, [])

  // Load ClickUp members when integrations load
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

  // Listen for OAuth popup completions
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.ok && typeof e.data?.type === 'string' && e.data.type.endsWith('-oauth')) {
        api.integrations.status().then(setIntegrations).catch(() => {})
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [])

  // Derived filter options
  const phases = useMemo(() => distinct(projects.map(p => p.phase).filter(Boolean)), [projects])
  const leads = useMemo(() => distinct(projects.map(p => p.owner_team).filter(Boolean)), [projects])
  const cities = useMemo(() => distinct(projects.map(p => p.city).filter(Boolean)), [projects])

  const onHoldCount = useMemo(() => projects.filter(p => p.status === 'on_hold').length, [projects])
  const issueCount = useMemo(() => projects.filter(p => p.validation && (p.validation.error_count > 0 || p.validation.warning_count > 0)).length, [projects])

  // Filtered list
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
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(uid)) next.delete(uid)
      else next.add(uid)
      return next
    })
  }

  const toggleSelected = (uid: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(uid)) next.delete(uid)
      else next.add(uid)
      return next
    })
  }

  const togglePreambleExpanded = (uid: string) => {
    setPreambleExpanded(prev => {
      const next = new Set(prev)
      if (next.has(uid)) next.delete(uid)
      else next.add(uid)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selected.size === filtered.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(filtered.map(p => p.uid)))
    }
  }

  // Actions
  const handleRender = async () => {
    setRendering(true)
    setFeedback('')
    try {
      const result = await api.bfaTodo.render()
      if (result.error) {
        setFeedback(result.error)
        setFeedbackErr(true)
      } else {
        setFeedback(`Rendered ${result.project_count} projects`)
        setFeedbackErr(false)
        load()
      }
    } catch (e: any) {
      setFeedback(e.message ?? 'Render failed')
      setFeedbackErr(true)
    }
    setRendering(false)
  }

  const handleDeploySelected = async () => {
    if (!docId.trim() || selected.size === 0) return
    setDeploying(true)
    setFeedback('')
    // Persist doc ID
    api.config.save({ bfa_todo_doc_id: docId.trim() }).catch(() => {})
    try {
      const result = await api.bfaTodo.deploySelected(docId.trim(), Array.from(selected))
      if (result.error) {
        setFeedback(result.error)
        setFeedbackErr(true)
      } else {
        setFeedback(`Deployed ${result.deployed} projects (${result.errors} errors)`)
        setFeedbackErr(result.errors > 0)
      }
    } catch (e: any) {
      setFeedback(e.message ?? 'Deploy failed')
      setFeedbackErr(true)
    }
    setDeploying(false)
  }

  const handleImportExcel = async () => {
    if (!excelPath.trim()) return
    setImportingExcel(true)
    setFeedback('')
    try {
      const result = await api.bfaTodo.importExcel(excelPath.trim())
      if (result.error) {
        setFeedback(result.error)
        setFeedbackErr(true)
      } else {
        setFeedback(`Imported ${result.project_count ?? ''} projects from Excel`)
        setFeedbackErr(false)
        load()
      }
    } catch (e: any) {
      setFeedback(e.message ?? 'Excel import failed')
      setFeedbackErr(true)
    }
    setImportingExcel(false)
  }

  const handleImportHtml = async () => {
    if (!htmlPath.trim()) return
    setImportingHtml(true)
    setFeedback('')
    try {
      const result = await api.bfaTodo.importHtml(htmlPath.trim())
      if (result.error) {
        setFeedback(result.error)
        setFeedbackErr(true)
      } else {
        setFeedback(`Imported ${result.project_count} projects from HTML source`)
        setFeedbackErr(false)
        load()
      }
    } catch (e: any) {
      setFeedback(e.message ?? 'HTML import failed')
      setFeedbackErr(true)
    }
    setImportingHtml(false)
  }

  const handleGoogleConnect = async () => {
    const ok = await openOAuthPopup(api.google.auth, 'google-oauth')
    if (ok) {
      setFeedback('Connected to Google')
      setFeedbackErr(false)
      api.integrations.status().then(setIntegrations).catch(() => {})
    } else {
      setFeedback('Google connection cancelled or failed')
      setFeedbackErr(true)
    }
  }

  const handleGoogleDisconnect = async () => {
    try {
      await api.config.save({ google_token: '', google_account_name: '' })
      setFeedback('Disconnected from Google')
      setFeedbackErr(false)
      api.integrations.status().then(setIntegrations).catch(() => {})
    } catch {
      setFeedback('Disconnect failed')
      setFeedbackErr(true)
    }
  }

  const googleConnected = integrations?.google.configured ?? false
  const googleAccount = integrations?.google.account ?? ''

  return (
    <ModuleLayout module="bfa-todo" activePage="overview">
      <div className="flex flex-col gap-3" style={{ height: 'calc(100vh - 48px)' }}>
        {loading ? (
          <p className="text-sm text-ws-text-secondary py-8 text-center">Loading...</p>
        ) : (
          <>
            {/* Source ingestion bar */}
            <div style={{ border: '1px solid var(--border)', background: 'var(--bg-surface)', padding: '10px 14px', fontFamily: 'var(--font-sans)' }}>
              <div className="flex flex-wrap items-center gap-3" style={{ fontSize: '13px' }}>
                <span style={{ fontWeight: 600, color: 'var(--fg-secondary)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Source</span>
                <select
                  className="filter-select"
                  value={source}
                  onChange={e => setSource(e.target.value as SourceType)}
                  style={{ fontSize: '12px' }}
                >
                  <option value="bfa-html">BFA HTML</option>
                  <option value="monday-excel">Monday Excel</option>
                  <option value="clickup" disabled>ClickUp (coming soon)</option>
                </select>

                {source === 'bfa-html' && (
                  <>
                    <input
                      type="text"
                      className="setting-input"
                      value={htmlPath}
                      onChange={e => setHtmlPath(e.target.value)}
                      placeholder="Path to BFA HTML data directory..."
                      style={{ width: '340px', fontSize: '12px' }}
                      onKeyDown={e => { if (e.key === 'Enter') handleImportHtml() }}
                    />
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={handleImportHtml}
                      disabled={importingHtml || !htmlPath.trim()}
                    >
                      {importingHtml ? 'Importing...' : 'Re-import'}
                    </button>
                  </>
                )}

                {source === 'monday-excel' && (
                  <>
                    <Upload size={14} style={{ color: 'var(--fg-secondary)', flexShrink: 0 }} />
                    <input
                      type="text"
                      className="setting-input"
                      value={excelPath}
                      onChange={e => setExcelPath(e.target.value)}
                      placeholder="Path to Monday .xlsx export..."
                      style={{ width: '300px', fontSize: '12px' }}
                      onKeyDown={e => { if (e.key === 'Enter') handleImportExcel() }}
                    />
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={handleImportExcel}
                      disabled={importingExcel || !excelPath.trim()}
                    >
                      {importingExcel ? 'Importing...' : 'Import'}
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* Filter bar */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative flex-1 min-w-[200px] max-w-sm">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--fg-disabled)' }} />
                <input
                  type="text"
                  className="search-input w-full pl-8"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Search projects..."
                />
              </div>
              <select className="filter-select" value={filterPhase} onChange={e => setFilterPhase(e.target.value)}>
                <option value="">Phase</option>
                {phases.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
              <select className="filter-select" value={filterLead} onChange={e => setFilterLead(e.target.value)}>
                <option value="">Lead</option>
                {leads.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
              <select className="filter-select" value={filterCity} onChange={e => setFilterCity(e.target.value)}>
                <option value="">City</option>
                {cities.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
              {onHoldCount > 0 && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '12px', color: 'var(--fg-secondary)', fontFamily: 'var(--font-sans)', cursor: 'pointer', userSelect: 'none' }}>
                  <input
                    type="checkbox"
                    checked={showOnHold}
                    onChange={e => setShowOnHold(e.target.checked)}
                    style={{ accentColor: 'var(--accent)' }}
                  />
                  On Hold ({onHoldCount})
                </label>
              )}
              {issueCount > 0 && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '12px', color: 'var(--color-warning, #b45309)', fontFamily: 'var(--font-sans)', cursor: 'pointer', userSelect: 'none' }}>
                  <input
                    type="checkbox"
                    checked={showIssuesOnly}
                    onChange={e => setShowIssuesOnly(e.target.checked)}
                    style={{ accentColor: 'var(--color-warning, #b45309)' }}
                  />
                  Issues ({issueCount})
                </label>
              )}
            </div>

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

            {/* Preamble blocks */}
            {preambles.length > 0 && (
              <div style={{ border: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2 px-3 py-1.5" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)', fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)' }}>
                  <span style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Preamble
                  </span>
                </div>
                {preambles.map(pre => (
                  <div key={pre.uid} style={{ borderBottom: '1px solid var(--border)' }}>
                    <div
                      className="flex items-center gap-2"
                      style={{ padding: '6px 12px', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}
                      onClick={() => togglePreambleExpanded(pre.uid)}
                    >
                      <ChevronRight
                        size={14}
                        className={clsx('transition-transform shrink-0', preambleExpanded.has(pre.uid) && 'rotate-90')}
                        style={{ color: 'var(--fg-secondary)' }}
                      />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--fg)' }}>
                        {pre.title}
                      </span>
                      <Badge variant="neutral" size="xs">{pre.type === 'preamble' ? 'overview' : 'lists'}</Badge>
                    </div>
                    {preambleExpanded.has(pre.uid) && (
                      <PreambleCompositionView uid={pre.uid} />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Project list */}
            <div className="flex-1 overflow-y-auto" style={{ border: '1px solid var(--border)' }}>
              {/* Select all header */}
              <div className="flex items-center gap-2 px-3 py-1.5" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)', fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)' }}>
                <input
                  type="checkbox"
                  checked={filtered.length > 0 && selected.size === filtered.length}
                  onChange={toggleSelectAll}
                  style={{ accentColor: 'var(--accent)' }}
                />
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

            {/* Action bar */}
            <div className="flex flex-wrap items-center gap-3" style={{ paddingTop: '4px', fontFamily: 'var(--font-sans)' }}>
              <button className="btn btn-sm" onClick={handleRender} disabled={rendering}>
                <Play size={12} />
                {rendering ? 'Rendering...' : 'Render All'}
              </button>

              <span style={{ width: '1px', height: '20px', background: 'var(--border)' }} />

              <span style={{ fontWeight: 600, color: 'var(--fg-secondary)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Target</span>
              <select
                className="filter-select"
                value={target}
                onChange={e => setTarget(e.target.value as TargetType)}
                style={{ fontSize: '12px' }}
              >
                <option value="none">None (local only)</option>
                <option value="google-docs">Google Docs</option>
                <option value="clickup" disabled>ClickUp (coming soon)</option>
              </select>

              {target === 'google-docs' && (
                <>
                  {/* Google account status */}
                  {googleConnected ? (
                    <>
                      <span style={{ fontSize: '11px', color: 'var(--fg-secondary)', background: 'var(--bg-surface)', padding: '2px 8px', border: '1px solid var(--border)', borderRadius: '2px' }}>
                        {googleAccount || 'Google connected'}
                      </span>
                      <button
                        className="btn btn-sm"
                        onClick={handleGoogleDisconnect}
                        style={{ fontSize: '11px' }}
                      >
                        Disconnect
                      </button>
                    </>
                  ) : integrations?.google.oauth_available ? (
                    <button className="btn btn-sm btn-primary" onClick={handleGoogleConnect}>
                      Connect Google
                    </button>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--fg-disabled)', fontStyle: 'italic' }}>
                      Google not configured
                    </span>
                  )}

                  {googleConnected && (
                    <>
                      <input
                        type="text"
                        className="setting-input"
                        value={docId}
                        onChange={e => setDocId(e.target.value)}
                        placeholder="Google Doc ID..."
                        style={{
                          width: '240px',
                          fontSize: '12px',
                          borderColor: !docId.trim() ? 'var(--color-warning)' : undefined,
                        }}
                        onKeyDown={e => { if (e.key === 'Enter') handleDeploySelected() }}
                      />
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={handleDeploySelected}
                        disabled={deploying || !docId.trim() || selected.size === 0}
                      >
                        <Send size={12} />
                        {deploying ? 'Deploying...' : `Deploy Selected (${selected.size})`}
                      </button>
                    </>
                  )}
                </>
              )}

              <FeedbackMessage message={feedback} isError={feedbackErr} />
            </div>
          </>
        )}
      </div>
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Project Row
// ---------------------------------------------------------------------------

function ProjectRow({
  project, isExpanded, isSelected, memberMap, onToggleExpand, onToggleSelect, onProjectUpdated,
}: {
  project: BfaTodoProject
  isExpanded: boolean
  isSelected: boolean
  memberMap: Record<string, string>
  onToggleExpand: () => void
  onToggleSelect: () => void
  onProjectUpdated: () => void
}) {
  const leadTitle = memberMap[project.owner_team] || project.owner_team
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editFields, setEditFields] = useState({
    client: project.client,
    project_name: project.project_name,
    city: project.city,
    phase: project.phase,
    owner_team: project.owner_team,
  })

  const hasIssues = project.validation && (project.validation.error_count > 0 || project.validation.warning_count > 0)
  const hasErrors = project.validation && project.validation.error_count > 0
  const suggestions = project.validation?.items.filter(i => i.suggestion) ?? []

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditFields({
      client: project.client,
      project_name: project.project_name,
      city: project.city,
      phase: project.phase,
      owner_team: project.owner_team,
    })
    setEditing(true)
  }

  const cancelEdit = () => setEditing(false)

  const saveEdit = async () => {
    setSaving(true)
    try {
      const changes: Record<string, string> = {}
      if (editFields.client !== project.client) changes.client = editFields.client
      if (editFields.project_name !== project.project_name) changes.project_name = editFields.project_name
      if (editFields.city !== project.city) changes.city = editFields.city
      if (editFields.phase !== project.phase) changes.phase = editFields.phase
      if (editFields.owner_team !== project.owner_team) changes.owner_team = editFields.owner_team
      if (Object.keys(changes).length > 0) {
        await api.bfaTodo.updateProject(project.uid, changes)
        onProjectUpdated()
      }
      setEditing(false)
    } catch {
      // stay in edit mode
    } finally {
      setSaving(false)
    }
  }

  const applySuggestion = (field: string, value: string) => {
    setEditFields(prev => ({ ...prev, [field]: value }))
  }

  if (editing) {
    return (
      <div style={{ borderBottom: '1px solid var(--border)', background: 'rgba(63, 92, 110, 0.06)', fontFamily: 'var(--font-sans)' }}>
        <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {/* Row 1: client — project_name */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              className="setting-input"
              value={editFields.client}
              onChange={e => setEditFields(prev => ({ ...prev, client: e.target.value }))}
              placeholder="Client"
              style={{ fontSize: '12px', width: '180px', fontWeight: 600 }}
            />
            <span style={{ color: 'var(--fg-secondary)', fontSize: '13px' }}>—</span>
            <input
              type="text"
              className="setting-input"
              value={editFields.project_name}
              onChange={e => setEditFields(prev => ({ ...prev, project_name: e.target.value }))}
              placeholder="Project name"
              style={{ fontSize: '12px', flex: 1, fontWeight: 600 }}
            />
          </div>
          {/* Row 2: city, phase, team */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              className="setting-input"
              value={editFields.city}
              onChange={e => setEditFields(prev => ({ ...prev, city: e.target.value }))}
              placeholder="City"
              style={{ fontSize: '12px', width: '140px' }}
            />
            <input
              type="text"
              className="setting-input"
              value={editFields.phase}
              onChange={e => setEditFields(prev => ({ ...prev, phase: e.target.value }))}
              placeholder="Phase"
              style={{ fontSize: '12px', width: '140px' }}
            />
            <input
              type="text"
              className="setting-input"
              value={editFields.owner_team}
              onChange={e => setEditFields(prev => ({ ...prev, owner_team: e.target.value }))}
              placeholder="Team"
              style={{ fontSize: '12px', width: '80px' }}
            />
            <div style={{ flex: 1 }} />
            <button className="btn btn-sm btn-primary" onClick={saveEdit} disabled={saving} style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}>
              <Save size={11} /> {saving ? 'Saving...' : 'Save'}
            </button>
            <button className="btn btn-sm" onClick={cancelEdit} disabled={saving} style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}>
              <X size={11} /> Cancel
            </button>
          </div>
          {/* Suggestions */}
          {suggestions.length > 0 && (
            <div className="flex flex-wrap items-center gap-2" style={{ fontSize: '11px' }}>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className="btn btn-sm"
                  onClick={() => applySuggestion(s.field, s.suggestion!)}
                  style={{ fontSize: '11px', padding: '1px 6px', gap: 3, display: 'flex', alignItems: 'center', color: 'var(--color-warning, #b45309)' }}
                >
                  <Check size={10} /> {s.message}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ borderBottom: '1px solid var(--border)', background: isExpanded ? 'rgba(63, 92, 110, 0.04)' : undefined }}>
      {/* Summary row */}
      <div
        className="flex items-center gap-2"
        style={{ padding: '6px 12px', cursor: 'pointer', fontFamily: 'var(--font-sans)', opacity: project.status === 'on_hold' ? 0.55 : 1 }}
        onClick={onToggleExpand}
      >
        <input
          type="checkbox"
          checked={isSelected}
          onChange={e => { e.stopPropagation(); onToggleSelect() }}
          onClick={e => e.stopPropagation()}
          style={{ accentColor: 'var(--accent)' }}
        />
        <ChevronRight
          size={14}
          className={clsx('transition-transform shrink-0', isExpanded && 'rotate-90')}
          style={{ color: 'var(--fg-secondary)' }}
        />
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--fg)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {project.client} — {project.project_name}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <span style={{ fontSize: '11px', color: 'var(--fg-secondary)', minWidth: 80, textAlign: 'right' }}>{project.city}</span>
          <span style={{ width: 1, height: 12, background: 'var(--border)' }} />
          <Badge variant="phase" size="xs">{project.phase}</Badge>
          <Badge variant="neutral" size="xs" title={leadTitle}>{project.owner_team}</Badge>
          {project.status === 'on_hold' && <Badge variant="neutral" size="xs">ON HOLD</Badge>}
          {hasIssues && (
            <button
              onClick={startEdit}
              title={project.validation.items.map(i => i.message).join('\n')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex' }}
            >
              <AlertTriangle size={14} style={{ color: hasErrors ? 'var(--color-error, #dc2626)' : 'var(--color-warning, #b45309)' }} />
            </button>
          )}
          {!hasIssues && (
            <button
              onClick={startEdit}
              title="Edit fields"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', opacity: 0.3 }}
            >
              <Pencil size={12} style={{ color: 'var(--fg-secondary)' }} />
            </button>
          )}
        </div>
      </div>

      {/* Expanded detail — composition view */}
      {isExpanded && <ProjectCompositionView uid={project.uid} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ProjectCompositionView — iframe with full pipeline fidelity + per-section editing
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// IframeCompositionView — shared iframe with contenteditable editing
// ---------------------------------------------------------------------------

function IframeCompositionView({
  uid, fetchUrl, onSaveSection, title,
}: {
  uid: string
  fetchUrl: string
  onSaveSection: (sectionName: string, html: string) => Promise<any>
  title?: string
}) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(80)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [srcdoc, setSrcdoc] = useState<string | null>(null)
  const [editingSection, setEditingSection] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const originalHtmlRef = useRef<string>('')

  const fetchHtml = useCallback(() => {
    setLoading(true)
    setError(false)
    fetch(fetchUrl)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.text()
      })
      .then(html => {
        setSrcdoc(html)
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }, [fetchUrl])

  useEffect(() => { fetchHtml() }, [fetchHtml])

  // Auto-size iframe to content
  const resizeIframe = useCallback(() => {
    const iframe = iframeRef.current
    if (!iframe) return
    try {
      const doc = iframe.contentDocument
      if (doc?.body) {
        requestAnimationFrame(() => {
          const h = doc.body.scrollHeight
          if (h > 0) setHeight(h + 8)
        })
      }
    } catch { /* cross-origin */ }
  }, [])

  const onLoad = useCallback(() => {
    resizeIframe()
    // Inject hover styles for editable sections into the iframe
    const doc = iframeRef.current?.contentDocument
    if (!doc) return
    const style = doc.createElement('style')
    style.textContent = `
      [data-section] { position: relative; transition: outline 0.12s; }
      [data-section]:hover { outline: 1px dashed rgba(63, 92, 110, 0.3); outline-offset: 2px; cursor: pointer; }
      [data-section].editing { outline: 2px solid #3F5C6E; outline-offset: 2px; cursor: text; }
      [data-section].editing:focus { outline: 2px solid #3F5C6E; }
    `
    doc.head.appendChild(style)

    // Click handler: click a section to start editing
    doc.body.addEventListener('click', (e: Event) => {
      const target = (e.target as HTMLElement).closest('[data-section]') as HTMLElement | null
      if (!target) return
      const secName = target.dataset.section
      if (secName) {
        window.postMessage({ type: 'bfa-edit-section', uid, section: secName }, '*')
      }
    })
  }, [uid, resizeIframe])

  // Listen for edit requests from inside the iframe
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'bfa-edit-section' && e.data.uid === uid) {
        const secName = e.data.section
        if (editingSection === secName) return // already editing
        startEditInIframe(secName)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  })

  const startEditInIframe = useCallback((secName: string) => {
    const doc = iframeRef.current?.contentDocument
    if (!doc) return
    // Cancel any current edit
    if (editingSection) {
      const prev = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
      if (prev) {
        prev.contentEditable = 'false'
        prev.classList.remove('editing')
        prev.innerHTML = originalHtmlRef.current
      }
    }
    const el = doc.querySelector(`[data-section="${secName}"]`) as HTMLElement | null
    if (!el) return
    originalHtmlRef.current = el.innerHTML
    el.contentEditable = 'true'
    el.classList.add('editing')
    el.style.outline = 'none' // let CSS class handle it
    el.focus()
    setEditingSection(secName)
    // Re-measure after content might change
    requestAnimationFrame(resizeIframe)
  }, [editingSection, resizeIframe])

  const cancelEdit = useCallback(() => {
    const doc = iframeRef.current?.contentDocument
    if (!doc || !editingSection) return
    const el = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
    if (el) {
      el.contentEditable = 'false'
      el.classList.remove('editing')
      el.innerHTML = originalHtmlRef.current
    }
    setEditingSection(null)
  }, [editingSection])

  const saveEdit = useCallback(async () => {
    const doc = iframeRef.current?.contentDocument
    if (!doc || !editingSection) return
    const el = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
    if (!el) return

    setSaving(true)
    try {
      await onSaveSection(editingSection, el.innerHTML)
      el.contentEditable = 'false'
      el.classList.remove('editing')
      setEditingSection(null)
      // Re-fetch to get updated render
      fetchHtml()
    } catch {
      // stay in edit mode
    } finally {
      setSaving(false)
    }
  }, [editingSection, onSaveSection, fetchHtml])

  if (loading) {
    return (
      <div style={{ padding: '4px 40px 12px', fontSize: '12px', color: 'var(--fg-secondary)', fontFamily: 'var(--font-sans)' }}>
        Loading...
      </div>
    )
  }

  if (error || !srcdoc) {
    return (
      <div style={{ padding: '4px 40px 12px', fontSize: '12px', color: 'var(--color-error)', fontFamily: 'var(--font-sans)' }}>
        Failed to load HTML
      </div>
    )
  }

  return (
    <div style={{ padding: '2px 12px 8px 40px' }}>
      {/* Edit toolbar — appears when editing a section */}
      {editingSection && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, fontFamily: 'var(--font-sans)' }}>
          <span style={{ fontSize: '11px', color: 'var(--fg-secondary)' }}>
            Editing section — click to edit text, then:
          </span>
          <button
            className="btn btn-sm btn-primary"
            onClick={saveEdit}
            disabled={saving}
            style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}
          >
            <Save size={11} /> {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            className="btn btn-sm"
            onClick={cancelEdit}
            disabled={saving}
            style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}
          >
            <X size={11} /> Cancel
          </button>
        </div>
      )}
      <iframe
        ref={iframeRef}
        srcDoc={srcdoc}
        onLoad={onLoad}
        style={{
          width: '100%',
          height: `${height}px`,
          border: 'none',
          display: 'block',
          background: '#fff',
        }}
        title={title || uid}
      />
    </div>
  )
}

function ProjectCompositionView({ uid }: { uid: string }) {
  return (
    <IframeCompositionView
      uid={uid}
      fetchUrl={`/api/bfa-todo/projects/${uid}/html`}
      onSaveSection={(sectionName, html) => api.bfaTodo.updateSection(uid, sectionName, html)}
      title={`Project ${uid}`}
    />
  )
}

function PreambleCompositionView({ uid }: { uid: string }) {
  return (
    <IframeCompositionView
      uid={uid}
      fetchUrl={`/api/bfa-todo/preambles/${uid}/html`}
      onSaveSection={(sectionName, html) => api.bfaTodo.updatePreambleSection(uid, sectionName, html)}
      title={`Preamble ${uid}`}
    />
  )
}
