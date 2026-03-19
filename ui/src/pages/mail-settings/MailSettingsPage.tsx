import { useState, useEffect } from 'react'
import { Mail, Search, Play, Square, RefreshCw } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { CardShell } from '@/components/settings/CardShell'
import { StatusBadge } from '@/components/settings/StatusBadge'
import { FieldRow } from '@/components/settings/FieldRow'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'

interface DiscoveredAccount {
  name: string
  has_inbox: string
}

export function MailSettingsPage() {
  return (
    <ModuleLayout module="mail" activePage="settings">
      <header className="header">
        <h1>Mail Settings</h1>
      </header>
      <MailServiceCard />
    </ModuleLayout>
  )
}

function MailServiceCard() {
  const [enabled, setEnabled] = useState(false)
  const [running, setRunning] = useState(false)
  const [interval, setIntervalVal] = useState(30)
  const [accounts, setAccounts] = useState<DiscoveredAccount[]>([])
  const [scanning, setScanning] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)

  const loadStatus = () => {
    fetch('/mail/status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setEnabled(data.enabled)
          setRunning(data.running)
          setIntervalVal(data.poll_interval)
        }
      })
      .catch(() => {})
  }

  useEffect(() => { loadStatus() }, [])

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

  const toggleEnabled = async (checked: boolean) => {
    setEnabled(checked)
    await save({ mail_enabled: checked })
    if (checked) {
      await fetch('/mail/start', { method: 'POST' })
    } else {
      await fetch('/mail/stop', { method: 'POST' })
    }
    loadStatus()
  }

  const handleScan = async () => {
    setScanning(true)
    setFeedback('')
    try {
      const response = await fetch('/mail/scan-accounts')
      if (response.ok) {
        const data = await response.json()
        setAccounts(data)
        if (data.length === 0) {
          setFeedback('No Outlook accounts found. Is Outlook running?')
          setFeedbackErr(true)
        } else {
          setFeedback(`Found ${data.length} account${data.length !== 1 ? 's' : ''}`)
          setFeedbackErr(false)
        }
      }
    } catch {
      setFeedback('Could not connect to Outlook')
      setFeedbackErr(true)
    }
    setScanning(false)
  }

  return (
    <CardShell
      icon={<Mail size={18} />}
      iconBg="icon-blue"
      title="Mail Service"
      badge={<StatusBadge ok={running} label={running ? 'Running' : 'Stopped'} />}
    >
      {/* Scan for accounts */}
      <FieldRow label="Accounts">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
          <div className="field-row-inline">
            <button
              className="btn btn-sm btn-primary"
              onClick={handleScan}
              disabled={scanning}
            >
              <Search size={12} />
              {scanning ? 'Scanning...' : 'Scan Outlook'}
            </button>
          </div>
          {accounts.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {accounts.map(acc => (
                <div
                  key={acc.name}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    padding: '6px 10px', background: 'var(--bg-surface)', borderRadius: '2px',
                    fontFamily: 'var(--font-sans)', fontSize: '13px',
                  }}
                >
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                    background: acc.has_inbox === 'true' ? 'var(--color-success)' : 'var(--fg-disabled)',
                  }} />
                  <span style={{ flex: 1, color: 'var(--fg)' }}>{acc.name}</span>
                  {acc.has_inbox === 'true' ? (
                    <span style={{ fontSize: '11px', color: 'var(--fg-secondary)' }}>Inbox found</span>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--fg-disabled)' }}>No inbox</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </FieldRow>

      {/* Enable + interval */}
      <FieldRow label="Polling">
        <div className="field-row-inline">
          <label className="toggle">
            <input
              type="checkbox"
              checked={enabled}
              onChange={e => toggleEnabled(e.target.checked)}
            />
            <span className="toggle-slider" />
          </label>
          <select
            className="setting-input"
            value={interval}
            onChange={e => setIntervalVal(Number(e.target.value))}
            style={{ width: '130px' }}
          >
            <option value={10}>10 seconds</option>
            <option value={30}>30 seconds</option>
            <option value={60}>1 minute</option>
            <option value={120}>2 minutes</option>
            <option value={300}>5 minutes</option>
            <option value={600}>10 minutes</option>
          </select>
          <button
            className="btn btn-sm"
            disabled={saving}
            onClick={() => save({ mail_poll_interval: interval })}
          >
            Save
          </button>
        </div>
      </FieldRow>

      {/* Service controls */}
      <FieldRow label="Service">
        <div className="field-row-inline">
          <button
            className="btn btn-sm"
            onClick={async () => { await fetch('/mail/start', { method: 'POST' }); loadStatus() }}
            disabled={running}
          >
            <Play size={12} /> Start
          </button>
          <button
            className="btn btn-sm"
            onClick={async () => { await fetch('/mail/stop', { method: 'POST' }); loadStatus() }}
            disabled={!running}
          >
            <Square size={12} /> Stop
          </button>
          <button className="btn btn-sm" onClick={loadStatus}>
            <RefreshCw size={12} />
          </button>
        </div>
      </FieldRow>

      <FeedbackMessage message={feedback} isError={feedbackErr} />
    </CardShell>
  )
}
