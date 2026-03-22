import { useState, useEffect, useRef, useCallback } from 'react'
import { ArrowLeft, Settings, Plug, Terminal, Activity } from 'lucide-react'
import { CardShell } from '@/components/settings/CardShell'
import { StatusBadge } from '@/components/settings/StatusBadge'
import { FieldRow } from '@/components/settings/FieldRow'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { IntegrationCard, PROVIDERS } from '@/components/integrations'
import type { SourceType } from '@/components/integrations'
import { useIntegrationStatus } from '@/hooks/useIntegrationStatus'
import { useOAuthConnect } from '@/hooks/useOAuthConnect'
import { api } from '@/lib/api'

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
  const { status, refresh } = useIntegrationStatus()
  const oauth = useOAuthConnect(refresh)

  if (!status) return null

  return (
    <div className="settings-tab-cards">
      {/* Google Workspace */}
      <IntegrationCard
        provider={PROVIDERS.google}
        connected={status.google.configured}
        source={status.google.configured ? 'oauth' as SourceType : 'none'}
        account={status.google.account}
        onConnect={status.google.oauth_available
          ? () => oauth.connect('Google', api.google.auth, 'google-oauth')
          : undefined}
        onDisconnect={status.google.configured
          ? () => oauth.disconnect('Google', 'google_token', 'google_account_name')
          : undefined}
      />

      {/* ClickUp */}
      <IntegrationCard
        provider={PROVIDERS.clickup}
        connected={status.clickup.configured}
        source={status.clickup.source as SourceType}
        onConnect={status.clickup.oauth_available && !status.clickup.configured
          ? () => oauth.connect('ClickUp', api.clickup.auth, 'clickup-oauth')
          : undefined}
        onDisconnect={status.clickup.configured && status.clickup.source === 'config'
          ? () => oauth.disconnect('ClickUp', 'clickup_token', '')
          : undefined}
      >
        {status.clickup.configured && <ClickUpStatus />}
      </IntegrationCard>

      {/* Monday.com */}
      <IntegrationCard
        provider={PROVIDERS.monday}
        connected={status.monday.configured}
        source={status.monday.configured ? 'oauth' as SourceType : 'none'}
        account={status.monday.account}
        onConnect={status.monday.oauth_available
          ? () => oauth.connect('Monday', api.monday.auth, 'monday-oauth')
          : undefined}
        onDisconnect={status.monday.configured
          ? () => oauth.disconnect('Monday', 'monday_token', 'monday_account_name')
          : undefined}
      />

      {/* Exchange — managed in Contacts Settings */}

      {/* AutoArt */}
      <IntegrationCard
        provider={PROVIDERS.autoart}
        connected={status.autoart?.paired ?? false}
        source={status.autoart?.paired ? 'pairing' as SourceType : 'none'}
      >
        <PairingFields />
      </IntegrationCard>

      <FeedbackMessage message={oauth.feedback} isError={oauth.feedbackErr} />
    </div>
  )
}

// --------------------------------------------------------------------------
// ClickUp Configuration (expanded fields inside IntegrationCard)
// --------------------------------------------------------------------------

function ClickUpStatus() {
  const [workspace, setWorkspace] = useState('')

  useEffect(() => {
    api.clickup.validate().then(v => {
      if (v.ok) setWorkspace(v.workspace ?? '')
    }).catch(() => {})
  }, [])

  if (!workspace) return null

  return (
    <FieldRow label="Workspace">
      <span className="configured-value">{workspace}</span>
    </FieldRow>
  )
}

// ==========================================================================
// System tab
// ==========================================================================

function SystemTab() {
  return (
    <div className="settings-tab-cards">
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

// --------------------------------------------------------------------------
// Pairing fields (rendered inside AutoArt IntegrationCard)
// --------------------------------------------------------------------------

function PairingFields() {
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

  if (paired === null) return null

  return paired ? (
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
  )
}
