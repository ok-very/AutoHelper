import { useState, useEffect, useRef, useCallback } from 'react'
import { Server, RefreshCw, Clock, List, Terminal } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { CardShell } from '@/components/settings/CardShell'
import { StatusBadge } from '@/components/settings/StatusBadge'
import { FieldRow } from '@/components/settings/FieldRow'
import { ConnectedValue } from '@/components/settings/ConnectedValue'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { WiringManifest } from '@/components/integrations'
import { CopyButton } from '@/ui/atoms'
import { api } from '@/lib/api'

export function ContactsSettingsPage() {
  return (
    <ModuleLayout module="contacts" activePage="settings">
      <header className="header">
        <h1>Contacts Settings</h1>
      </header>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <WiringManifest module="contacts" />
        <ExchangeConnectionCard />
        <ConsoleCard />
        <ContactSyncCard />
        <SyncStatusCard />
        <SyncHistoryCard />
      </div>
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Exchange Connection
// ---------------------------------------------------------------------------

type ExchangePhase = 'no-creds' | 'ready' | 'connecting' | 'connected' | 'error'

function ExchangeConnectionCard() {
  const [phase, setPhase] = useState<ExchangePhase>('no-creds')
  const [orgName, setOrgName] = useState('')
  const [deviceCode, setDeviceCode] = useState('')
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const busy = useRef(false)

  // ── Mount: check credentials + session state ─────────────────
  useEffect(() => {
    api.integrations.status().catch(() => null).then(async (intStatus) => {
      const hasCreds = intStatus?.exchange?.configured
      setLoaded(true)
      if (!hasCreds) { setPhase('no-creds'); return }
      try {
        const st = await api.contacts.exchangeStatus()
        if (st.state === 'connected') {
          const test = await api.contacts.testExchange()
          setOrgName(test.message ?? '')
          setPhase('connected')
        } else {
          setPhase('ready')
        }
      } catch {
        setPhase('ready')
      }
    })
  }, [])

  // ── Heartbeat while connected — detect dead session ─────────
  useEffect(() => {
    if (phase !== 'connected') return
    const iv = setInterval(async () => {
      try {
        const st = await api.contacts.exchangeStatus()
        if (st.state !== 'connected') setPhase('ready')
      } catch { /* keep checking */ }
    }, 10_000)
    return () => clearInterval(iv)
  }, [phase])

  // ── Poll during connecting phase ─────────────────────────────
  useEffect(() => {
    if (phase !== 'connecting') return
    const start = Date.now()
    const iv = setInterval(async () => {
      try {
        const st = await api.contacts.exchangeStatus()
        if (st.state === 'connected') {
          const test = await api.contacts.testExchange()
          setOrgName(test.message ?? '')
          setPhase('connected')
        } else if (st.state === 'disconnected' && st.error) {
          setError(st.error)
          setPhase('error')
        } else if (Date.now() - start > 120_000) {
          setError('MFA timed out')
          setPhase('error')
        }
      } catch { /* keep polling */ }
    }, 3000)
    return () => clearInterval(iv)
  }, [phase])

  // ── Actions ──────────────────────────────────────────────────
  const connect = async () => {
    if (busy.current) return
    busy.current = true
    try {
      const data = await api.contacts.connectExchange()
      if (data.connected) {
        setOrgName(data.message ?? '')
        setPhase('connected')
      } else if (data.device_code) {
        window.open(data.url, '_blank')
        setDeviceCode(data.code)
        setPhase('connecting')
      } else {
        setError(data.message ?? 'Connect failed')
        setPhase('error')
      }
    } catch {
      setError('Network error')
      setPhase('error')
    }
    busy.current = false
  }

  const disconnect = async () => {
    try { await api.contacts.disconnectExchange() } catch { /* ok */ }
    setOrgName('')
    setDeviceCode('')
    setPhase('ready')
  }

  if (!loaded) return null

  const badge = (() => {
    switch (phase) {
      case 'connected': return <StatusBadge ok label="Connected" />
      case 'connecting': return <span className="conn-badge off">Connecting</span>
      case 'error': return <span className="conn-badge off">Error</span>
      default: return null
    }
  })()

  return (
    <CardShell icon={<Server size={20} />} iconBg="icon-blue" title="Exchange Connection" badge={badge}>
      {phase === 'no-creds' && (
        <span className="not-configured">No credentials configured. Set exchange_email in Settings or .env</span>
      )}

      {phase === 'connecting' && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          padding: '10px 12px', borderRadius: '6px',
          background: 'var(--ws-bg-elevated, #f5f5f5)',
          border: '1px solid var(--ws-border, #e0e0e0)',
        }}>
          <span style={{ fontSize: '12px', opacity: 0.7 }}>Enter code in browser:</span>
          <code style={{ fontSize: '18px', fontWeight: 700, letterSpacing: '0.1em' }}>{deviceCode}</code>
          <CopyButton value={deviceCode} />
        </div>
      )}

      {phase === 'connected' && orgName && (
        <FieldRow label="Organization">
          <span className="configured-value">{orgName.replace(/^Connected to /, '')}</span>
        </FieldRow>
      )}

      {phase === 'error' && (
        <FeedbackMessage message={error} isError />
      )}

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        {(phase === 'ready' || phase === 'error') && (
          <button className="btn btn-sm" onClick={connect}>Connect</button>
        )}
        {phase === 'connected' && (
          <>
            <button className="btn btn-sm" onClick={async () => {
              const data = await api.contacts.testExchange()
              setOrgName(data.message ?? '')
              if (!data.connected) { setPhase('ready') }
            }}>Test</button>
            <button className="btn btn-sm" style={{ color: 'var(--color-error)' }} onClick={disconnect}>Disconnect</button>
          </>
        )}
      </div>
    </CardShell>
  )
}

// ---------------------------------------------------------------------------
// Contact Sync Settings
// ---------------------------------------------------------------------------

function ContactSyncCard() {
  const [cfg, setCfg] = useState<Record<string, unknown>>({})
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.config.get().then(c => setCfg(c)).catch(() => {})
  }, [])

  const save = async (patch: Record<string, unknown>) => {
    setSaving(true)
    setFeedback('')
    try {
      const r = await api.config.save(patch)
      if (r.ok) {
        setCfg(prev => ({ ...prev, ...patch }))
        setFeedback('\u2713 Saved')
        setFeedbackErr(false)
      } else {
        setFeedback('\u2717 Error')
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('\u2717 Network error')
      setFeedbackErr(true)
    }
    setSaving(false)
  }

  const enabled = Boolean(cfg.contact_sync_enabled)

  return (
    <CardShell icon={<RefreshCw size={20} />} iconBg="icon-green" title="Contact Sync">
      <FieldRow label="Enabled">
        <label className="toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => save({ contact_sync_enabled: e.target.checked })}
          />
          <span className="toggle-slider" />
        </label>
      </FieldRow>

      {enabled && (
        <>
          <FieldRow label="CSV Path">
            <ConnectedValue
              value={(cfg.contact_sync_csv_path as string) ?? ''}
              placeholder="C:\\path\\to\\contacts.csv"
              onSave={v => save({ contact_sync_csv_path: v })}
            />
          </FieldRow>

          <FieldRow label="Interval (sec)">
            <input
              type="number"
              className="setting-input"
              value={Number(cfg.contact_sync_interval ?? 300)}
              onChange={e => setCfg(prev => ({ ...prev, contact_sync_interval: Number(e.target.value) }))}
              onBlur={() => save({ contact_sync_interval: Number(cfg.contact_sync_interval ?? 300) })}
              min={30}
              max={86400}
              style={{ width: '100px' }}
            />
          </FieldRow>

          <FieldRow label="Work Hours Start">
            <input
              type="number"
              className="setting-input"
              value={Number(cfg.contact_sync_work_start ?? 8)}
              onChange={e => save({ contact_sync_work_start: Number(e.target.value) })}
              min={0}
              max={23}
              style={{ width: '80px' }}
            />
          </FieldRow>

          <FieldRow label="Work Hours End">
            <input
              type="number"
              className="setting-input"
              value={Number(cfg.contact_sync_work_end ?? 18)}
              onChange={e => save({ contact_sync_work_end: Number(e.target.value) })}
              min={0}
              max={23}
              style={{ width: '80px' }}
            />
          </FieldRow>

          <FieldRow label="Timezone">
            <input
              type="text"
              className="setting-input"
              value={(cfg.contact_sync_timezone as string) ?? 'America/Vancouver'}
              onChange={e => setCfg(prev => ({ ...prev, contact_sync_timezone: e.target.value }))}
              onBlur={() => save({ contact_sync_timezone: cfg.contact_sync_timezone })}
              style={{ width: '200px' }}
            />
          </FieldRow>

          <FieldRow label="Batch Size">
            <input
              type="number"
              className="setting-input"
              value={Number(cfg.contact_sync_batch_size ?? 50)}
              onChange={e => save({ contact_sync_batch_size: Number(e.target.value) })}
              min={1}
              max={500}
              style={{ width: '80px' }}
            />
          </FieldRow>

          <FieldRow label="Managed Prefix">
            <input
              type="text"
              className="setting-input"
              value={(cfg.contact_sync_managed_prefix as string) ?? ''}
              onChange={e => setCfg(prev => ({ ...prev, contact_sync_managed_prefix: e.target.value }))}
              onBlur={() => save({ contact_sync_managed_prefix: cfg.contact_sync_managed_prefix })}
              placeholder="[AutoHelper]"
              style={{ width: '200px' }}
            />
          </FieldRow>

          <FieldRow label="Dry Run">
            <label className="toggle">
              <input
                type="checkbox"
                checked={Boolean(cfg.contact_sync_dry_run)}
                onChange={e => save({ contact_sync_dry_run: e.target.checked })}
              />
              <span className="toggle-slider" />
            </label>
          </FieldRow>
        </>
      )}

      <FeedbackMessage message={feedback} isError={feedbackErr} />
    </CardShell>
  )
}

// ---------------------------------------------------------------------------
// Sync Status
// ---------------------------------------------------------------------------

function SyncStatusCard() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [dryRun, setDryRun] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)

  const load = () => {
    api.contacts.status()
      .then(s => setStatus(s))
      .catch(() => setStatus(null))
  }

  useEffect(() => { load() }, [])

  const syncNow = async () => {
    setSyncing(true)
    setFeedback('')
    try {
      await api.config.save({ contact_sync_dry_run: dryRun })
      const data = await api.contacts.sync()
      if (data.status === 'started') {
        setFeedback(`\u2713 ${data.message}${dryRun ? ' (dry run)' : ''}`)
        setFeedbackErr(false)
        load()
      } else {
        setFeedback(`\u2717 ${data.message ?? 'Sync failed'}`)
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('\u2717 Network error')
      setFeedbackErr(true)
    }
    setSyncing(false)
  }

  return (
    <CardShell icon={<Clock size={20} />} iconBg="icon-amber" title="Sync Status">
      {status ? (
        <>
          <FieldRow label="Enabled">
            <StatusBadge ok={Boolean(status.enabled)} label={status.enabled ? 'Yes' : 'No'} />
          </FieldRow>
          {status.last_sync && (
            <FieldRow label="Last Sync">{String(status.last_sync)}</FieldRow>
          )}
          {status.next_sync && (
            <FieldRow label="Next Sync">{String(status.next_sync)}</FieldRow>
          )}
          {status.last_result && (
            <FieldRow label="Last Result">{String(status.last_result)}</FieldRow>
          )}
        </>
      ) : (
        <span className="not-configured">Could not load sync status</span>
      )}

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button className="btn btn-sm btn-primary" onClick={syncNow} disabled={syncing}>
          {syncing ? 'Syncing\u2026' : 'Sync Now'}
        </button>
        {syncing && (
          <button className="btn btn-sm" style={{ color: 'var(--color-error)' }} onClick={async () => {
            await api.contacts.stopSync().catch(() => {})
            setFeedback('Stop requested — finishing current batch')
            setFeedbackErr(false)
          }}>Stop</button>
        )}
        <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', cursor: 'pointer' }}>
          <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} />
          Dry run
        </label>
        <FeedbackMessage message={feedback} isError={feedbackErr} />
      </div>
    </CardShell>
  )
}

// ---------------------------------------------------------------------------
// Sync History
// ---------------------------------------------------------------------------

function SyncHistoryCard() {
  const [history, setHistory] = useState<Record<string, unknown>[]>([])

  useEffect(() => {
    api.contacts.history()
      .then(h => setHistory(Array.isArray(h) ? h : []))
      .catch(() => {})
  }, [])

  return (
    <CardShell icon={<List size={20} />} iconBg="icon-blue" title="Sync History">
      {history.length === 0 ? (
        <span className="not-configured">No sync history available</span>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="ranking-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Status</th>
                <th>Created</th>
                <th>Updated</th>
                <th>Deleted</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row, i) => (
                <tr key={i}>
                  <td>{String(row.time ?? row.timestamp ?? '')}</td>
                  <td>{String(row.status ?? '')}</td>
                  <td>{String(row.created ?? 0)}</td>
                  <td>{String(row.updated ?? 0)}</td>
                  <td>{String(row.deleted ?? 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </CardShell>
  )
}

// ---------------------------------------------------------------------------
// Console (live logs via SSE)
// ---------------------------------------------------------------------------

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
