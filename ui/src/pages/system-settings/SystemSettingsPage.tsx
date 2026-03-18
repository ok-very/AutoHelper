import { useState, useEffect, useRef, useCallback } from 'react'
import { ArrowLeft, Settings, Plug, Terminal, Activity, Link2, MousePointerClick } from 'lucide-react'
import { CardShell } from '@/components/settings/CardShell'
import { StatusBadge } from '@/components/settings/StatusBadge'
import { FieldRow } from '@/components/settings/FieldRow'
import { ConnectedValue } from '@/components/settings/ConnectedValue'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'
import type { IntegrationStatus, IntegrationFieldStatus } from '@/lib/api'

// ==========================================================================
// Tab definitions
// ==========================================================================

type Tab = 'general' | 'integrations' | 'system'

const TABS: { id: Tab; label: string; icon: typeof Settings }[] = [
  { id: 'general', label: 'General', icon: Settings },
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'system', label: 'System', icon: Terminal },
]

// ==========================================================================
// Page shell
// ==========================================================================

export function SystemSettingsPage() {
  const [tab, setTab] = useState<Tab>(() => {
    const hash = window.location.hash.slice(1) as Tab
    return TABS.some(t => t.id === hash) ? hash : 'general'
  })

  const switchTab = (t: Tab) => {
    setTab(t)
    window.location.hash = t
  }

  return (
    <div className="system-settings">
      <a href="/" className="system-settings-back">
        <ArrowLeft size={14} /> Home
      </a>
      <div className="system-settings-header">
        <h1>Settings</h1>
      </div>
      <div className="settings-layout">
        <nav className="settings-nav">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`settings-nav-item ${tab === id ? 'active' : ''}`}
              onClick={() => switchTab(id)}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>
        <div className="settings-content">
          {tab === 'general' && <GeneralTab />}
          {tab === 'integrations' && <IntegrationsTab />}
          {tab === 'system' && <SystemTab />}
        </div>
      </div>
    </div>
  )
}

// ==========================================================================
// Shared helpers
// ==========================================================================

function EnvBadge() {
  return <span className="env-badge">ENV</span>
}

function SourceAwareField({
  field, label, placeholder, configKey, onSave,
}: {
  field: IntegrationFieldStatus
  label: string
  placeholder?: string
  configKey: string
  onSave: (key: string, value: string) => Promise<void>
}) {
  if (field.source === 'env') {
    return (
      <FieldRow label={label}>
        <div className="field-row-inline">
          <span className="configured-value">{field.value}</span>
          <EnvBadge />
        </div>
      </FieldRow>
    )
  }
  return (
    <FieldRow label={label}>
      <ConnectedValue
        value={field.value}
        placeholder={placeholder}
        onSave={v => onSave(configKey, v)}
      />
    </FieldRow>
  )
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

      // Fallback: if popup closes without postMessage
      const timer = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(timer)
          window.removeEventListener('message', handler)
          // Give a small delay for any in-flight postMessage
          setTimeout(() => resolve(false), 300)
        }
      }, 500)
    } catch {
      resolve(false)
    }
  })
}

// ==========================================================================
// General tab
// ==========================================================================

function GeneralTab() {
  return (
    <div className="settings-tab-cards">
      <ServiceStatusCard />
      <GeneralSettingsCard />
    </div>
  )
}

function ServiceStatusCard() {
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    Promise.all([
      api.health().catch(() => null),
      api.status().catch(() => null),
    ]).then(([h, s]) => {
      setHealth(h)
      setStatus(s)
      if (!h && !s) setError(true)
    })
  }, [])

  const isOk = health !== null && !error
  const mode = (status?.mode as string) ?? 'unknown'
  const dbOk = (health?.database as string) === 'ok' || (health?.db as string) === 'ok'

  return (
    <CardShell
      icon={<Activity size={18} />}
      iconBg={isOk ? 'icon-green' : 'icon-red'}
      title="Service"
      badge={<StatusBadge ok={isOk} label={isOk ? 'Healthy' : 'Error'} />}
    >
      <FieldRow label="Service">{isOk ? 'Running' : 'Unreachable'}</FieldRow>
      <FieldRow label="Mode">{mode}</FieldRow>
      <FieldRow label="Database">
        <StatusBadge ok={dbOk} label={dbOk ? 'Connected' : 'Unknown'} />
      </FieldRow>
      {health?.version != null && <FieldRow label="Version">{String(health.version)}</FieldRow>}
    </CardShell>
  )
}

function GeneralSettingsCard() {
  const [logLevel, setLogLevel] = useState('INFO')
  const [roots, setRoots] = useState<string[]>([])
  const [excludes, setExcludes] = useState('')
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)
  const [typingPath, setTypingPath] = useState(false)
  const [pathDraft, setPathDraft] = useState('')

  useEffect(() => {
    api.config.get().then(cfg => {
      setLogLevel((cfg.log_level as string) ?? 'INFO')
      setRoots((cfg.allowed_roots as string[]) ?? [])
      const ex = cfg.excludes
      setExcludes(Array.isArray(ex) ? ex.join(', ') : (ex as string) ?? '')
    }).catch(() => {
      setFeedback('Could not load config')
      setFeedbackErr(true)
    })
  }, [])

  const save = async (patch: Record<string, unknown>) => {
    setSaving(true)
    setFeedback('')
    try {
      const r = await api.config.save(patch)
      if (r.ok) { setFeedback('Saved'); setFeedbackErr(false) }
      else { setFeedback('Error saving'); setFeedbackErr(true) }
    } catch {
      setFeedback('Network error'); setFeedbackErr(true)
    }
    setSaving(false)
  }

  const addRoot = async () => {
    const d = await api.config.selectFolder()
    if (d.path && !roots.includes(d.path)) {
      const next = [...roots, d.path]
      setRoots(next)
      await save({ allowed_roots: next })
    }
  }

  const removeRoot = (idx: number) => {
    const next = roots.filter((_, i) => i !== idx)
    setRoots(next)
    save({ allowed_roots: next })
  }

  const addTypedPath = () => {
    const p = pathDraft.trim()
    if (p && !roots.includes(p)) {
      const next = [...roots, p]
      setRoots(next)
      save({ allowed_roots: next })
    }
    setPathDraft('')
    setTypingPath(false)
  }

  return (
    <CardShell icon={<Settings size={18} />} iconBg="icon-blue" title="Configuration">
      <FieldRow label="Log Level">
        <select
          className="setting-input"
          value={logLevel}
          onChange={e => { setLogLevel(e.target.value); save({ log_level: e.target.value }) }}
          style={{ width: '140px' }}
        >
          {['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(l => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
      </FieldRow>

      <div>
        <span className="field-row-label" style={{ display: 'block', marginBottom: '8px' }}>Allowed Roots</span>
        {roots.length === 0 ? (
          <span className="not-configured">No roots configured</span>
        ) : (
          roots.map((r, i) => (
            <div key={i} className="folder-list-item">
              <span className="configured-value">{r}</span>
              <button className="btn btn-sm btn-danger" onClick={() => removeRoot(i)}>&times;</button>
            </div>
          ))
        )}

        {typingPath ? (
          <div className="path-input-row">
            <input
              type="text"
              className="setting-input"
              value={pathDraft}
              onChange={e => setPathDraft(e.target.value)}
              placeholder="C:\path\to\folder"
              style={{ flex: 1 }}
              autoFocus
              onKeyDown={e => {
                if (e.key === 'Enter') addTypedPath()
                if (e.key === 'Escape') { setTypingPath(false); setPathDraft('') }
              }}
            />
            <button className="btn btn-sm btn-primary" onClick={addTypedPath}>Add</button>
            <button className="btn btn-sm" onClick={() => { setTypingPath(false); setPathDraft('') }}>Cancel</button>
          </div>
        ) : (
          <div className="path-input-row">
            <button className="btn btn-sm" onClick={addRoot}>Browse</button>
            <button className="btn btn-sm" onClick={() => setTypingPath(true)}>Type path</button>
          </div>
        )}
      </div>

      <FieldRow label="Excludes">
        <div className="field-row-inline" style={{ flex: 1 }}>
          <input
            type="text"
            className="setting-input"
            value={excludes}
            onChange={e => setExcludes(e.target.value)}
            placeholder="pattern1, pattern2"
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-sm btn-primary"
            disabled={saving}
            onClick={() => save({ excludes: excludes.split(',').map(s => s.trim()).filter(Boolean) })}
          >
            Save
          </button>
        </div>
      </FieldRow>

      <FeedbackMessage message={feedback} isError={feedbackErr} />
    </CardShell>
  )
}

// ==========================================================================
// Integrations tab
// ==========================================================================

function IntegrationsTab() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null)
  const [config, setConfig] = useState<Record<string, unknown>>({})

  const refresh = useCallback(() => {
    Promise.all([
      api.integrations.status().catch(() => null),
      api.config.get().catch(() => ({})),
    ]).then(([s, cfg]) => {
      if (s) setStatus(s)
      setConfig(cfg as Record<string, unknown>)
    })
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // Listen for any OAuth popup messages
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.ok && typeof e.data?.type === 'string' && e.data.type.endsWith('-oauth')) {
        refresh()
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [refresh])

  if (!status) return null

  return (
    <div className="settings-tab-cards">
      <OAuthConnectionsCard status={status} onRefresh={refresh} />
      <ClickUpConfigCard status={status} config={config} setConfig={setConfig} onRefresh={refresh} />
    </div>
  )
}

// --------------------------------------------------------------------------
// OAuth Connections
// --------------------------------------------------------------------------

function OAuthConnectionsCard({
  status,
  onRefresh,
}: {
  status: IntegrationStatus
  onRefresh: () => void
}) {
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)

  const connect = async (
    provider: string,
    fetchAuth: () => Promise<{ url: string }>,
    messageType: string,
  ) => {
    setFeedback('')
    const ok = await openOAuthPopup(fetchAuth, messageType)
    if (ok) {
      setFeedback(`Connected to ${provider}`)
      setFeedbackErr(false)
      onRefresh()
    } else {
      setFeedback(`${provider} connection cancelled or failed`)
      setFeedbackErr(true)
    }
  }

  const disconnect = async (provider: string, tokenKey: string, accountKey: string) => {
    try {
      await api.config.save({ [tokenKey]: '', [accountKey]: '' })
      setFeedback(`Disconnected from ${provider}`)
      setFeedbackErr(false)
      onRefresh()
    } catch {
      setFeedback('Disconnect failed')
      setFeedbackErr(true)
    }
  }

  return (
    <CardShell
      icon={<Plug size={18} />}
      iconBg="icon-blue"
      title="Connections"
      subtitle="Connect external services to enable data sync and document generation."
    >
      {/* Google Workspace */}
      <div className="integration-row">
        <div className="integration-row-icon icon-blue">
          <svg width="18" height="18" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
        </div>
        <div className="integration-row-info">
          <div className="integration-row-name">Google Workspace</div>
          <div className="integration-row-desc">
            {status.google.configured && status.google.account
              ? `Connected as ${status.google.account}`
              : 'Drive, Sheets, Calendar'}
          </div>
        </div>
        <div className="integration-row-actions">
          {status.google.configured ? (
            <>
              <StatusBadge ok label="Connected" />
              <button className="btn btn-sm" onClick={() => disconnect('Google', 'google_token', 'google_account_name')}>
                Disconnect
              </button>
            </>
          ) : status.google.oauth_available ? (
            <button className="btn btn-sm btn-primary" onClick={() => connect('Google', api.google.auth, 'google-oauth')}>
              Connect
            </button>
          ) : (
            <span className="not-configured">Not configured</span>
          )}
        </div>
      </div>

      {/* Monday.com */}
      <div className="integration-row">
        <div className="integration-row-icon icon-amber">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><circle cx="4.5" cy="17.5" r="3" fill="#FF3D57"/><circle cx="12" cy="11" r="3" fill="#FFCB00"/><circle cx="19.5" cy="17.5" r="3" fill="#00CA72"/><rect x="3" y="6" width="3" height="12" rx="1.5" fill="#FF3D57"/><rect x="10.5" y="4" width="3" height="8" rx="1.5" fill="#FFCB00"/><rect x="18" y="8" width="3" height="10" rx="1.5" fill="#00CA72"/></svg>
        </div>
        <div className="integration-row-info">
          <div className="integration-row-name">Monday.com</div>
          <div className="integration-row-desc">
            {status.monday.configured && status.monday.account
              ? `Connected as ${status.monday.account}`
              : 'Project boards and item sync'}
          </div>
        </div>
        <div className="integration-row-actions">
          {status.monday.configured ? (
            <>
              <StatusBadge ok label="Connected" />
              <button className="btn btn-sm" onClick={() => disconnect('Monday', 'monday_token', 'monday_account_name')}>
                Disconnect
              </button>
            </>
          ) : status.monday.oauth_available ? (
            <button className="btn btn-sm btn-primary" onClick={() => connect('Monday', api.monday.auth, 'monday-oauth')}>
              Connect
            </button>
          ) : (
            <span className="not-configured">Not configured</span>
          )}
        </div>
      </div>

      {/* ClickUp */}
      <div className="integration-row">
        <div className="integration-row-icon icon-purple">
          <MousePointerClick size={16} />
        </div>
        <div className="integration-row-info">
          <div className="integration-row-name">ClickUp</div>
          <div className="integration-row-desc">
            {status.clickup.configured
              ? 'Project management and template sync'
              : 'Task management, templates, artist roster'}
          </div>
        </div>
        <div className="integration-row-actions">
          {status.clickup.configured ? (
            <>
              <StatusBadge ok label="Connected" />
              {status.clickup.source === 'config' && (
                <button className="btn btn-sm" onClick={async () => {
                  await api.config.save({ clickup_token: '' })
                  onRefresh()
                }}>
                  Disconnect
                </button>
              )}
              {status.clickup.source === 'env' && <EnvBadge />}
            </>
          ) : status.clickup.oauth_available ? (
            <button className="btn btn-sm btn-primary" onClick={() => connect('ClickUp', api.clickup.auth, 'clickup-oauth')}>
              Connect
            </button>
          ) : (
            <span className="not-configured">Not configured</span>
          )}
        </div>
      </div>

      {/* Exchange */}
      {status.exchange.configured && (
        <div className="integration-row">
          <div className="integration-row-icon icon-blue">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><rect x="2" y="4" width="20" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none"/><path d="M2 8l10 6 10-6" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>
          </div>
          <div className="integration-row-info">
            <div className="integration-row-name">Exchange</div>
            <div className="integration-row-desc">{status.exchange.email.value || 'Mail and contacts'}</div>
          </div>
          <div className="integration-row-actions">
            <StatusBadge ok label="Connected" />
            {status.exchange.source === 'env' && <EnvBadge />}
          </div>
        </div>
      )}

      <FeedbackMessage message={feedback} isError={feedbackErr} />
    </CardShell>
  )
}

// --------------------------------------------------------------------------
// ClickUp Configuration (expanded settings)
// --------------------------------------------------------------------------

function ClickUpConfigCard({
  status,
  config,
  setConfig,
  onRefresh,
}: {
  status: IntegrationStatus
  config: Record<string, unknown>
  setConfig: React.Dispatch<React.SetStateAction<Record<string, unknown>>>
  onRefresh: () => void
}) {
  const [connected, setConnected] = useState<boolean | null>(null)
  const [workspace, setWorkspace] = useState('')
  const [testing, setTesting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)

  useEffect(() => {
    if (status.clickup.configured) {
      api.clickup.validate().then(v => {
        setConnected(v.ok)
        if (v.workspace) setWorkspace(v.workspace)
      }).catch(() => setConnected(false))
    } else {
      setConnected(false)
    }
  }, [status.clickup.configured])

  const testConnection = async () => {
    setTesting(true)
    setFeedback('')
    try {
      const v = await api.clickup.validate()
      setConnected(v.ok)
      if (v.ok) {
        setFeedback('Connection verified')
        setFeedbackErr(false)
        if (v.workspace) setWorkspace(v.workspace)
      } else {
        setFeedback(v.error ?? 'Validation failed')
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('Network error')
      setFeedbackErr(true)
    }
    setTesting(false)
  }

  const saveField = async (key: string, value: string) => {
    try {
      const r = await api.config.save({ [key]: value })
      if (r.ok) {
        setConfig(prev => ({ ...prev, [key]: value }))
        setFeedback('Saved')
        setFeedbackErr(false)
        onRefresh()
      }
    } catch {
      setFeedback('Save failed')
      setFeedbackErr(true)
    }
  }

  // Don't show unless ClickUp is configured
  if (!status.clickup.configured) return null

  const cu = status.clickup

  return (
    <CardShell
      icon={<MousePointerClick size={18} />}
      iconBg="icon-purple"
      title="ClickUp"
      subtitle="Workspace configuration, template sync, and artist roster."
      badge={connected !== null ? <StatusBadge ok={connected} label={connected ? 'Active' : 'Error'} /> : undefined}
    >
      {connected && workspace && (
        <FieldRow label="Workspace">{workspace}</FieldRow>
      )}

      <SourceAwareField field={cu.workspace_id} label="Workspace ID" configKey="clickup_workspace_id" onSave={saveField} />
      <SourceAwareField field={cu.space_id} label="Space ID" configKey="clickup_space_id" onSave={saveField} />
      <SourceAwareField field={cu.list_id} label="Template List" configKey="clickup_list_id" onSave={saveField} />

      <FieldRow label="Template Sync">
        <label className="toggle">
          <input
            type="checkbox"
            checked={Boolean(config.clickup_template_sync)}
            onChange={e => saveField('clickup_template_sync', String(e.target.checked))}
          />
          <span className="toggle-slider" />
        </label>
      </FieldRow>

      <FieldRow label="Artist List">
        <ConnectedValue
          value={String(config.clickup_artist_list_id ?? '')}
          placeholder="List ID for artist records"
          onSave={v => saveField('clickup_artist_list_id', v)}
        />
      </FieldRow>

      <ArtistSyncRow listId={String(config.clickup_artist_list_id ?? '')} connected={connected === true} />

      <div className="field-row-inline">
        <button className="btn btn-sm" onClick={testConnection} disabled={testing}>
          {testing ? 'Testing\u2026' : 'Test Connection'}
        </button>
        <FeedbackMessage message={feedback} isError={feedbackErr} />
      </div>
    </CardShell>
  )
}

function ArtistSyncRow({ listId, connected }: { listId: string; connected: boolean }) {
  const [syncing, setSyncing] = useState(false)
  const [preview, setPreview] = useState<{ created: number; updated: number; unchanged: number; errors: string[] } | null>(null)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)

  const dryRun = async () => {
    if (!listId) { setFeedback('Set Artist List ID first'); setFeedbackErr(true); return }
    setSyncing(true); setFeedback('')
    try {
      const result = await api.clickup.artistSync(listId, true)
      setPreview(result)
      setFeedback(`Will create ${result.created}, update ${result.updated}, ${result.unchanged} unchanged`)
      setFeedbackErr(false)
    } catch (e) {
      setFeedback(`${e}`); setFeedbackErr(true)
    }
    setSyncing(false)
  }

  const apply = async () => {
    if (!listId) return
    setSyncing(true); setFeedback('')
    try {
      const result = await api.clickup.artistSync(listId, false)
      setPreview(null)
      setFeedback(`Created ${result.created}, updated ${result.updated}${result.errors.length ? `, ${result.errors.length} errors` : ''}`)
      setFeedbackErr(result.errors.length > 0)
    } catch (e) {
      setFeedback(`${e}`); setFeedbackErr(true)
    }
    setSyncing(false)
  }

  if (!connected) return null

  return (
    <FieldRow label="Artist Sync">
      <div className="field-row-inline" style={{ flexWrap: 'wrap' }}>
        <button className="btn btn-sm" onClick={dryRun} disabled={syncing || !listId}>
          {syncing ? 'Syncing\u2026' : 'Preview'}
        </button>
        {preview && (
          <button className="btn btn-sm btn-primary" onClick={apply} disabled={syncing}>
            Apply
          </button>
        )}
        <FeedbackMessage message={feedback} isError={feedbackErr} />
      </div>
    </FieldRow>
  )
}

// ==========================================================================
// System tab
// ==========================================================================

function SystemTab() {
  return (
    <div className="settings-tab-cards">
      <PairingCard />
      <ConsoleCard />
    </div>
  )
}

function ConsoleCard() {
  const [lines, setLines] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)
  const autoScroll = useRef(true)

  useEffect(() => {
    fetch('/logs?limit=100')
      .then(r => r.ok ? r.json() : [])
      .then((data: string[]) => { if (Array.isArray(data)) setLines(data) })
      .catch(() => {})

    const es = new EventSource('/logs/stream')
    es.onmessage = (e) => {
      setLines(prev => {
        const next = [...prev, e.data]
        return next.length > 500 ? next.slice(-500) : next
      })
    }
    return () => es.close()
  }, [])

  useEffect(() => {
    if (autoScroll.current && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [lines])

  const onScroll = useCallback(() => {
    if (!logRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = logRef.current
    autoScroll.current = scrollHeight - scrollTop - clientHeight < 40
  }, [])

  return (
    <CardShell icon={<Terminal size={18} />} iconBg="icon-blue" title="Console">
      <div ref={logRef} className="console-log" onScroll={onScroll}>
        {lines.map((line, i) => <div key={i}>{line}</div>)}
      </div>
    </CardShell>
  )
}

function PairingCard() {
  const [paired, setPaired] = useState<boolean | null>(null)
  const [pairCode, setPairCode] = useState('')
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    fetch('/pair/status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) setPaired(Boolean(data.paired))
      })
      .catch(() => setPaired(null))
  }, [])

  const doPair = async () => {
    if (!pairCode.trim()) return
    setLoading(true)
    setFeedback('')
    try {
      const r = await fetch('/pair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: pairCode.trim() }),
      })
      const data = await r.json()
      if (r.ok && data.ok) {
        setPaired(true)
        setFeedback('Paired successfully')
        setFeedbackErr(false)
        setPairCode('')
      } else {
        setFeedback(data.error ?? 'Pairing failed')
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('Network error')
      setFeedbackErr(true)
    }
    setLoading(false)
  }

  const doUnpair = async () => {
    setLoading(true)
    setConfirming(false)
    try {
      const r = await fetch('/pair', { method: 'DELETE' })
      if (r.ok) {
        setPaired(false)
        setFeedback('Unpaired')
        setFeedbackErr(false)
      }
    } catch {
      setFeedback('Error')
      setFeedbackErr(true)
    }
    setLoading(false)
  }

  return (
    <CardShell
      icon={<Link2 size={18} />}
      iconBg="icon-blue"
      title="AutoArt Pairing"
      subtitle="Link to the AutoArt backend for project context and data sync."
      badge={paired !== null ? <StatusBadge ok={paired} label={paired ? 'Paired' : 'Not paired'} /> : undefined}
    >
      {paired ? (
        confirming ? (
          <div className="inline-confirm">
            <span>Unpair from AutoArt? You will need a new code to re-pair.</span>
            <button className="btn btn-sm btn-danger" onClick={doUnpair} disabled={loading}>Unpair</button>
            <button className="btn btn-sm" onClick={() => setConfirming(false)}>Cancel</button>
          </div>
        ) : (
          <div className="field-row-inline">
            <button className="btn btn-sm" onClick={() => setConfirming(true)} disabled={loading}>Unpair</button>
            <FeedbackMessage message={feedback} isError={feedbackErr} />
          </div>
        )
      ) : (
        <>
          <FieldRow label="Pair Code">
            <div className="field-row-inline" style={{ flex: 1 }}>
              <input
                type="text"
                className="setting-input"
                value={pairCode}
                onChange={e => setPairCode(e.target.value)}
                placeholder="Enter pairing code"
                style={{ flex: 1 }}
                onKeyDown={e => { if (e.key === 'Enter') doPair() }}
              />
              <button className="btn btn-primary btn-sm" onClick={doPair} disabled={loading || !pairCode.trim()}>
                {loading ? 'Pairing\u2026' : 'Pair'}
              </button>
            </div>
          </FieldRow>
          <FeedbackMessage message={feedback} isError={feedbackErr} />
        </>
      )}
    </CardShell>
  )
}
