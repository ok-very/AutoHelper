import { useState, useEffect } from 'react'
import { Mail, FolderInput, Play, Square, RefreshCw } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { CardShell } from '@/components/settings/CardShell'
import { StatusBadge } from '@/components/settings/StatusBadge'
import { FieldRow } from '@/components/settings/FieldRow'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'

export function MailSettingsPage() {
  return (
    <ModuleLayout module="mail" activePage="settings">
      <header className="header">
        <h1>Mail Settings</h1>
      </header>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <MailServiceCard />
        <MailStorageCard />
      </div>
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Service control
// ---------------------------------------------------------------------------

function MailServiceCard() {
  const [enabled, setEnabled] = useState(false)
  const [running, setRunning] = useState(false)
  const [interval, setIntervalVal] = useState(30)
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

  return (
    <CardShell
      icon={<Mail size={18} />}
      iconBg="icon-blue"
      title="Mail Polling"
      badge={<StatusBadge ok={running} label={running ? 'Running' : 'Stopped'} />}
    >
      <FieldRow label="Enabled">
        <label className="toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => toggleEnabled(e.target.checked)}
          />
          <span className="toggle-slider" />
        </label>
      </FieldRow>

      <FieldRow label="Poll Interval">
        <div className="field-row-inline">
          <select
            className="setting-input"
            value={interval}
            onChange={e => setIntervalVal(Number(e.target.value))}
            style={{ width: '140px' }}
          >
            <option value={10}>10 seconds</option>
            <option value={30}>30 seconds</option>
            <option value={60}>1 minute</option>
            <option value={120}>2 minutes</option>
            <option value={300}>5 minutes</option>
            <option value={600}>10 minutes</option>
          </select>
          <button
            className="btn btn-sm btn-primary"
            disabled={saving}
            onClick={() => save({ mail_poll_interval: interval })}
          >
            Save
          </button>
        </div>
      </FieldRow>

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

// ---------------------------------------------------------------------------
// Storage — output path, ingest path (doubles as PST drop folder), import
// ---------------------------------------------------------------------------

function MailStorageCard() {
  const [outputPath, setOutputPath] = useState('')
  const [ingestPath, setIngestPath] = useState('')
  const [ingesting, setIngesting] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)

  useEffect(() => {
    fetch('/mail/status')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setOutputPath(data.output_path || '')
          setIngestPath(data.ingest_path || '')
        }
      })
      .catch(() => {})
  }, [])

  const save = async (key: string, value: string) => {
    setFeedback('')
    try {
      const r = await api.config.save({ [key]: value })
      if (r.ok) { setFeedback('Saved'); setFeedbackErr(false) }
      else { setFeedback('Error saving'); setFeedbackErr(true) }
    } catch {
      setFeedback('Network error'); setFeedbackErr(true)
    }
  }

  const browse = async (setter: (v: string) => void, configKey: string) => {
    const result = await api.config.selectFolder()
    if (result.path) {
      setter(result.path)
      await save(configKey, result.path)
    }
  }

  const handleIngest = async () => {
    if (!ingestPath.trim()) return
    setIngesting(true)
    setFeedback('')
    try {
      const response = await fetch('/mail/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_path: ingestPath.trim() }),
      })
      const result = await response.json()
      if (result.success) {
        setFeedback(`Ingested ${result.count ?? 0} emails`)
        setFeedbackErr(false)
      } else {
        setFeedback(result.error ?? 'Ingestion failed')
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('Network error'); setFeedbackErr(true)
    }
    setIngesting(false)
  }

  return (
    <CardShell
      icon={<FolderInput size={18} />}
      iconBg="icon-blue"
      title="Storage"
    >
      <FieldRow label="Email Output">
        <div className="field-row-inline" style={{ flex: 1 }}>
          <span className="configured-value" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {outputPath || 'Not set'}
          </span>
          <button className="btn btn-sm" onClick={() => browse(setOutputPath, 'mail_output_path')}>Browse</button>
        </div>
      </FieldRow>

      <FieldRow label="PST/OST Folder">
        <div className="field-row-inline" style={{ flex: 1 }}>
          <span className="configured-value" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {ingestPath || 'Not set'}
          </span>
          <button className="btn btn-sm" onClick={() => browse(setIngestPath, 'mail_ingest_path')}>Browse</button>
          <button
            className="btn btn-sm btn-primary"
            onClick={handleIngest}
            disabled={ingesting || !ingestPath.trim()}
          >
            {ingesting ? 'Importing...' : 'Import'}
          </button>
        </div>
      </FieldRow>

      <FeedbackMessage message={feedback} isError={feedbackErr} />
    </CardShell>
  )
}
