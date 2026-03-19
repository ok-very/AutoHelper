/**
 * ProjectContext — shows project stage, template suggestions, and ClickUp task linking
 * for an email matched to a project. Slots into MailDetailView between header and body.
 */

import { useState, useEffect, useCallback } from 'react'
import {
  Layers, ChevronRight, Mail, Link2, Loader2, CheckCircle2, ExternalLink
} from 'lucide-react'
import type { MailEmail } from '../types'

interface StageInfo {
  number: number
  name: string
  total: number
  completed: number
  progress: number
  is_active: boolean
  is_complete: boolean
}

interface TemplateReady {
  temp_id: string
  name: string
  template_key: string
}

interface StageReport {
  project_id: string
  project_name: string
  current_stage: number
  total_tasks: number
  completed_tasks: number
  overall_progress: number
  stages: StageInfo[]
  templates_ready: TemplateReady[]
  error: string | null
}

interface ProjectContextProps {
  email: MailEmail
}

export function ProjectContext({ email }: ProjectContextProps) {
  const [report, setReport] = useState<StageReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [linkingTask, setLinkingTask] = useState(false)
  const [linkFeedback, setLinkFeedback] = useState('')
  const [composing, setComposing] = useState<string | null>(null)
  const [composedHtml, setComposedHtml] = useState('')

  const projectId = email.project_id
  const linkedTaskId = (email.metadata as any)?.linked_task_id

  // Fetch stage report when project changes
  useEffect(() => {
    if (!projectId) {
      setReport(null)
      return
    }
    setLoading(true)
    fetch(`/api/projects/${projectId}/stage-report`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setReport(data) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [projectId])

  const handleLinkToTask = useCallback(async (taskTempId: string) => {
    if (!report || !email) return
    // Find the ClickUp task name from the template ready list
    // For now, use the temp_id — in future, we'd resolve to the actual ClickUp task ID
    setLinkingTask(true)
    setLinkFeedback('')
    try {
      // We need the actual ClickUp task ID, not temp_id
      // The stage report doesn't have it yet, so we use the link-task endpoint
      // which takes a ClickUp task ID. For the MVP, we'll show a prompt.
      const taskId = prompt('Enter ClickUp task ID to link this email to:')
      if (!taskId) { setLinkingTask(false); return }

      const response = await fetch(`/mail/emails/${email.id}/link-task`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: taskId, auto_thread: true }),
      })
      const result = await response.json()
      if (result.ok) {
        setLinkFeedback('Linked to ClickUp task — future thread emails will auto-post')
      } else {
        setLinkFeedback(result.detail || 'Failed to link')
      }
    } catch {
      setLinkFeedback('Failed to connect')
    }
    setLinkingTask(false)
  }, [email, report])

  const handleCompose = useCallback(async (templateKey: string) => {
    if (!projectId) return
    setComposing(templateKey)
    try {
      const response = await fetch(`/api/projects/${projectId}/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_key: templateKey }),
      })
      const result = await response.json()
      if (result.html_body) {
        setComposedHtml(result.html_body)
      }
    } catch {
      setComposedHtml('')
    }
  }, [projectId])

  const handleCreateDraft = useCallback(async () => {
    if (!composedHtml || !composing) return
    try {
      await fetch('/mail/draft/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: '',
          subject: '',
          body: composedHtml,
        }),
      })
      setLinkFeedback('Draft created in Outlook')
      setTimeout(() => setLinkFeedback(''), 3000)
    } catch {
      setLinkFeedback('Failed to create draft')
    }
    setComposing(null)
    setComposedHtml('')
  }, [composedHtml, composing])

  if (!projectId) return null
  if (loading) {
    return (
      <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--bg-surface)', display: 'flex', alignItems: 'center', gap: 8, fontSize: '13px', color: 'var(--fg-secondary)' }}>
        <Loader2 size={14} className="animate-spin" /> Loading project context...
      </div>
    )
  }
  if (!report || report.error) return null

  const activeStage = report.stages.find(s => s.is_active)

  return (
    <div style={{ borderBottom: '1px solid var(--bg-surface)' }}>
      {/* Stage progress bar */}
      <div style={{ padding: '16px 24px', background: 'var(--bg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Layers size={14} style={{ color: 'var(--accent)' }} />
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--fg)' }}>
              {report.project_name}
            </span>
            {activeStage && (
              <span style={{
                fontSize: '11px', padding: '2px 10px', borderRadius: 10,
                background: 'rgba(63, 92, 110, 0.1)', color: 'var(--accent)',
                fontWeight: 600,
              }}>
                Stage {activeStage.number}: {activeStage.name}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: '11px', color: 'var(--fg-secondary)', fontFamily: 'var(--font-mono)' }}>
              {report.completed_tasks}/{report.total_tasks} tasks
            </span>
            {linkedTaskId && (
              <span style={{
                fontSize: '10px', padding: '2px 8px', borderRadius: 10,
                background: 'rgba(111, 127, 92, 0.1)', color: 'var(--color-success)',
                fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4,
              }}>
                <Link2 size={10} /> Linked
              </span>
            )}
          </div>
        </div>

        {/* Stage pills */}
        <div style={{ display: 'flex', gap: 3, marginBottom: 8 }}>
          {report.stages.map(s => (
            <div
              key={s.number}
              title={`Stage ${s.number}: ${s.name} (${s.completed}/${s.total})`}
              style={{
                flex: 1, height: 6, borderRadius: 3,
                background: s.is_complete
                  ? 'var(--color-success)'
                  : s.is_active
                    ? `linear-gradient(90deg, var(--accent) ${s.progress * 100}%, var(--bg-surface) ${s.progress * 100}%)`
                    : 'var(--bg-surface)',
                transition: 'background 0.3s',
              }}
            />
          ))}
        </div>

        {/* Action row */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {!linkedTaskId && (
            <button
              onClick={() => handleLinkToTask('')}
              disabled={linkingTask}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 10px', fontSize: '11px', fontWeight: 600,
                border: '1px solid var(--border)', borderRadius: 4,
                background: 'var(--bg-white)', color: 'var(--fg-secondary)',
                cursor: 'pointer', fontFamily: 'var(--font-sans)',
              }}
            >
              <Link2 size={12} />
              {linkingTask ? 'Linking...' : 'Link to ClickUp Task'}
            </button>
          )}
          {linkFeedback && (
            <span style={{ fontSize: '11px', color: 'var(--color-success)' }}>{linkFeedback}</span>
          )}
        </div>
      </div>

      {/* Templates ready for current stage */}
      {report.templates_ready.length > 0 && (
        <div style={{ padding: '12px 24px', background: 'var(--bg-white)', borderTop: '1px solid var(--bg-surface)' }}>
          <div style={{
            fontSize: '10px', fontWeight: 700, textTransform: 'uppercase',
            letterSpacing: '0.06em', color: 'var(--fg-disabled)', marginBottom: 8,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <Mail size={12} /> Templates Ready
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {report.templates_ready.map(t => (
              <div
                key={t.temp_id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '6px 10px', borderRadius: 4,
                  border: '1px solid var(--border)', background: 'var(--bg)',
                  fontSize: '12px', fontFamily: 'var(--font-sans)',
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--fg-disabled)', minWidth: 36 }}>
                  {t.template_key}
                </span>
                <span style={{ flex: 1, color: 'var(--fg)' }}>{t.name}</span>
                <button
                  onClick={() => handleCompose(t.template_key)}
                  style={{
                    padding: '2px 10px', fontSize: '11px', fontWeight: 600,
                    border: '1px solid var(--accent)', borderRadius: 3,
                    background: composing === t.template_key ? 'var(--accent)' : 'transparent',
                    color: composing === t.template_key ? 'var(--accent-fg)' : 'var(--accent)',
                    cursor: 'pointer', fontFamily: 'var(--font-sans)',
                  }}
                >
                  {composing === t.template_key ? 'Loading...' : 'Compose'}
                </button>
              </div>
            ))}
          </div>

          {/* Compose preview */}
          {composedHtml && composing && (
            <div style={{ marginTop: 12, border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                padding: '8px 12px', background: 'var(--bg-surface)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                borderBottom: '1px solid var(--border)',
              }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--fg-secondary)' }}>
                  Compose Preview
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={handleCreateDraft}
                    style={{
                      padding: '3px 10px', fontSize: '11px', fontWeight: 600,
                      background: 'var(--accent)', color: 'var(--accent-fg)',
                      border: 'none', borderRadius: 3, cursor: 'pointer',
                    }}
                  >
                    Create Outlook Draft
                  </button>
                  <button
                    onClick={() => { navigator.clipboard.writeText(composedHtml); setLinkFeedback('Copied'); setTimeout(() => setLinkFeedback(''), 2000) }}
                    style={{
                      padding: '3px 10px', fontSize: '11px', fontWeight: 600,
                      background: 'var(--bg-white)', color: 'var(--fg-secondary)',
                      border: '1px solid var(--border)', borderRadius: 3, cursor: 'pointer',
                    }}
                  >
                    Copy
                  </button>
                  <button
                    onClick={() => { setComposing(null); setComposedHtml('') }}
                    style={{
                      padding: '3px 10px', fontSize: '11px',
                      background: 'transparent', color: 'var(--fg-disabled)',
                      border: 'none', cursor: 'pointer',
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>
              <div
                style={{
                  padding: '16px', fontFamily: 'Calibri, Verdana, sans-serif',
                  fontSize: '11pt', lineHeight: 1.5, maxHeight: 300, overflowY: 'auto',
                }}
                dangerouslySetInnerHTML={{ __html: composedHtml }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
