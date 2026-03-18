import { useState, useEffect } from 'react'
import { Mail } from 'lucide-react'
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
      <MailPollingCard />
    </ModuleLayout>
  )
}

function MailPollingCard() {
  const [enabled, setEnabled] = useState(false)
  const [interval, setInterval_] = useState(60)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.config.get().then(cfg => {
      setEnabled(Boolean(cfg.mail_enabled))
      setInterval_(Number(cfg.mail_poll_interval ?? 60))
    }).catch(() => {
      setFeedback('\u2717 Could not load config')
      setFeedbackErr(true)
    })
  }, [])

  const save = async (patch: Record<string, unknown>) => {
    setSaving(true)
    setFeedback('')
    try {
      const r = await api.config.save(patch)
      if (r.ok) {
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

  return (
    <CardShell
      icon={<Mail size={20} />}
      iconBg="icon-blue"
      title="Mail Polling"
      badge={<StatusBadge ok={enabled} label={enabled ? 'Running' : 'Stopped'} />}
    >
      <FieldRow label="Enabled">
        <label className="toggle">
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => {
              setEnabled(e.target.checked)
              save({ mail_enabled: e.target.checked })
            }}
          />
          <span className="toggle-slider" />
        </label>
      </FieldRow>

      {enabled && (
        <FieldRow label="Poll Interval (sec)">
          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <input
              type="number"
              className="setting-input"
              value={interval}
              onChange={e => setInterval_(Number(e.target.value))}
              min={5}
              max={3600}
              style={{ width: '100px' }}
            />
            <button
              className="btn btn-sm btn-primary"
              disabled={saving}
              onClick={() => save({ mail_poll_interval: interval })}
            >
              Save
            </button>
          </div>
        </FieldRow>
      )}

      <FeedbackMessage message={feedback} isError={feedbackErr} />
    </CardShell>
  )
}
