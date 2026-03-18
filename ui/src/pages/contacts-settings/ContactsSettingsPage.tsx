import { useState, useEffect } from 'react'
import { Server, RefreshCw, Clock, List } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { CardShell } from '@/components/settings/CardShell'
import { StatusBadge } from '@/components/settings/StatusBadge'
import { FieldRow } from '@/components/settings/FieldRow'
import { ConnectedValue } from '@/components/settings/ConnectedValue'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'
import type { IntegrationStatus } from '@/lib/api'

export function ContactsSettingsPage() {
  return (
    <ModuleLayout module="contacts" activePage="settings">
      <header className="header">
        <h1>Contacts Settings</h1>
      </header>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <ExchangeConnectionCard />
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

function EnvBadge() {
  return (
    <span className="conn-badge ok" style={{ fontSize: '10px', padding: '1px 5px', letterSpacing: '0.05em' }}>
      ENV
    </span>
  )
}

function ExchangeConnectionCard() {
  const [email, setEmail] = useState('')
  const [hasPassword, setHasPassword] = useState(false)
  const [source, setSource] = useState<'env' | 'config' | 'none'>('none')
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    Promise.all([
      api.integrations.status().catch(() => null),
      api.config.get().catch(() => ({})),
    ]).then(([intStatus, cfg]) => {
      const ex = intStatus?.exchange
      if (ex) {
        setEmail(ex.email.value)
        setSource(ex.source)
        setHasPassword(ex.configured && ex.source !== 'none')
      } else {
        // Fallback to config if integrations endpoint unavailable
        setEmail(((cfg as Record<string, unknown>).exchange_email as string) ?? '')
        setHasPassword(Boolean((cfg as Record<string, unknown>).exchange_password))
      }
      setLoaded(true)
    })
  }, [])

  const isConfigured = email.length > 0
  const isEnv = source === 'env'

  const testConnection = async () => {
    setTesting(true)
    setFeedback('')
    try {
      const data = await api.contacts.testExchange()
      if (data.ok) {
        setFeedback('\u2713 Exchange connection successful')
        setFeedbackErr(false)
      } else {
        setFeedback(`\u2717 ${data.error ?? 'Connection failed'}`)
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('\u2717 Network error')
      setFeedbackErr(true)
    }
    setTesting(false)
  }

  const clear = async () => {
    try {
      const r = await api.config.save({ exchange_email: '', exchange_password: '' })
      if (r.ok) {
        setEmail('')
        setHasPassword(false)
        setSource('none')
        setFeedback('\u2713 Cleared')
        setFeedbackErr(false)
      }
    } catch {
      setFeedback('\u2717 Error')
      setFeedbackErr(true)
    }
  }

  if (!loaded) return null

  return (
    <CardShell
      icon={<Server size={20} />}
      iconBg="icon-blue"
      title="Exchange Connection"
      badge={<StatusBadge ok={isConfigured} label={isConfigured ? 'Configured' : 'Not configured'} />}
    >
      <FieldRow label="Email">
        {isEnv ? (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span className="configured-value">{email}</span>
            <EnvBadge />
          </div>
        ) : (
          <ConnectedValue
            value={email}
            placeholder="user@example.com"
            onSave={async (v) => {
              const r = await api.config.save({ exchange_email: v })
              if (r.ok) { setEmail(v); setSource('config'); setFeedback('\u2713 Saved'); setFeedbackErr(false) }
            }}
            onClear={clear}
          />
        )}
      </FieldRow>

      {!isEnv && (
        <FieldRow label="Password">
          <ConnectedValue
            value={hasPassword ? 'set' : ''}
            password
            placeholder="Exchange password"
            onSave={async (v) => {
              const r = await api.config.save({ exchange_password: v })
              if (r.ok) { setHasPassword(true); setFeedback('\u2713 Saved'); setFeedbackErr(false) }
            }}
            onClear={async () => {
              const r = await api.config.save({ exchange_password: '' })
              if (r.ok) { setHasPassword(false); setFeedback('\u2713 Cleared'); setFeedbackErr(false) }
            }}
          />
        </FieldRow>
      )}

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        {isConfigured && (
          <button className="btn btn-sm" onClick={testConnection} disabled={testing}>
            {testing ? 'Testing\u2026' : 'Test Connection'}
          </button>
        )}
        <FeedbackMessage message={feedback} isError={feedbackErr} />
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
      const data = await api.contacts.sync()
      if (data.ok) {
        setFeedback('\u2713 Sync complete')
        setFeedbackErr(false)
        load()
      } else {
        setFeedback(`\u2717 ${data.error ?? 'Sync failed'}`)
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
