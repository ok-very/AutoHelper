import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { clsx } from 'clsx'
import { RefreshCw, ChevronRight, Mail, ChevronDown } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { Badge } from '@ui/atoms'
import { api } from '@/lib/api'
import type { EmailTemplateData, EmailTemplateDef, RecipientRole } from '@/lib/types'

const STAGE_NAMES: Record<number, string> = {
  1: 'Project Initiation',
  2: 'Preliminary Public Art Plan',
  3: 'Detailed Public Art Plan',
  5: 'Artist Selection',
  6: 'Artist Orientation & Selection Panel #2',
  7: 'Artist Contract',
  10: 'Installation',
  11: 'Close-Out & Documentation',
}

const ROLE_LABELS: Record<RecipientRole, string> = {
  developer: 'Developer',
  city: 'City',
  artist: 'Artist',
  panel: 'Panel',
  internal: 'Internal',
}

const ROLE_VARIANTS: Record<RecipientRole, 'default' | 'info' | 'success' | 'warning' | 'neutral'> = {
  developer: 'default',
  city: 'info',
  artist: 'success',
  panel: 'warning',
  internal: 'neutral',
}

export function EmailTemplateMatrixPage() {
  const [data, setData] = useState<EmailTemplateData | null>(null)
  const [loading, setLoading] = useState(true)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [seeding, setSeeding] = useState(false)
  const [collapsedStages, setCollapsedStages] = useState<Set<number>>(new Set())
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set())
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    api.projects.emailTemplates.get()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const templatesByStage = useMemo(() => {
    if (!data) return new Map<number, EmailTemplateDef[]>()
    const map = new Map<number, EmailTemplateDef[]>()
    const sorted = [...data.templates].sort((a, b) => a.order - b.order)
    for (const t of sorted) {
      const stage = t.stage || 0
      if (!map.has(stage)) map.set(stage, [])
      map.get(stage)!.push(t)
    }
    return map
  }, [data])

  const toggleStage = (stage: number) => {
    setCollapsedStages(prev => {
      const next = new Set(prev)
      if (next.has(stage)) next.delete(stage)
      else next.add(stage)
      return next
    })
  }

  const toggleExpanded = (key: string) => {
    setExpandedKeys(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const handleFieldChange = useCallback((key: string, field: string, value: string) => {
    if (!data) return
    setData(prev => {
      if (!prev) return prev
      return {
        ...prev,
        templates: prev.templates.map(t =>
          t.key === key ? { ...t, [field]: value } : t
        ),
      }
    })

    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      api.projects.emailTemplates.updateTemplate({ key, [field]: value }).catch(() => {
        setFeedback('Failed to save')
        setFeedbackErr(true)
      })
    }, 800)
  }, [data])

  const handleRoleChange = useCallback((key: string, role: RecipientRole) => {
    handleFieldChange(key, 'recipient_role', role)
  }, [handleFieldChange])

  const handleSeed = async () => {
    setSeeding(true)
    setFeedback('')
    try {
      const result = await api.projects.emailTemplates.seed()
      setData(result)
      setFeedback(`Seeded ${result.templates.length} templates from markdown files`)
      setFeedbackErr(false)
    } catch (e: any) {
      setFeedback(e.message ?? 'Seed failed')
      setFeedbackErr(true)
    }
    setSeeding(false)
  }

  const stageNumbers = Array.from(templatesByStage.keys()).sort((a, b) => a - b)
  const totalCount = data?.templates.length ?? 0

  return (
    <ModuleLayout module="systems" activePage="email-templates">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {loading ? (
          <p className="not-configured">Loading...</p>
        ) : (
          <>
            {/* Toolbar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', border: '1px solid var(--border)', background: 'var(--bg)' }}>
              <Mail size={16} style={{ color: 'var(--fg-secondary)', flexShrink: 0 }} />
              <span style={{ fontFamily: 'var(--font-sans)', fontSize: '13px', color: 'var(--fg-secondary)' }}>
                {totalCount} templates across {stageNumbers.length} stages
              </span>
              <span style={{ flex: 1 }} />
              <button className="btn btn-sm" onClick={handleSeed} disabled={seeding}>
                <RefreshCw size={12} className={seeding ? 'animate-spin' : ''} />
                {seeding ? 'Seeding...' : 'Re-seed from Markdown'}
              </button>
            </div>
            <FeedbackMessage message={feedback} isError={feedbackErr} />

            {/* Template list */}
            {data && totalCount > 0 ? (
              <div style={{ border: '1px solid var(--border)' }}>
                {stageNumbers.map(stage => {
                  const templates = templatesByStage.get(stage) ?? []
                  const collapsed = collapsedStages.has(stage)

                  return (
                    <div key={stage}>
                      {/* Stage header */}
                      <div
                        onClick={() => toggleStage(stage)}
                        style={{
                          padding: '8px 12px',
                          background: 'var(--bg-surface)',
                          borderBottom: '1px solid var(--border)',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <ChevronRight
                          size={14}
                          className={clsx('transition-transform', !collapsed && 'rotate-90')}
                          style={{ color: 'var(--fg-secondary)' }}
                        />
                        <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-secondary)', fontFamily: 'var(--font-sans)' }}>
                          Stage {stage}: {STAGE_NAMES[stage] ?? `Stage ${stage}`}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--fg-disabled)', fontWeight: 400 }}>
                          ({templates.length})
                        </span>
                      </div>

                      {/* Template rows */}
                      {!collapsed && templates.map(tmpl => (
                        <TemplateRow
                          key={tmpl.key}
                          template={tmpl}
                          expanded={expandedKeys.has(tmpl.key)}
                          onToggleExpand={() => toggleExpanded(tmpl.key)}
                          onFieldChange={handleFieldChange}
                          onRoleChange={handleRoleChange}
                        />
                      ))}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div style={{ border: '1px solid var(--border)', padding: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Mail size={16} style={{ color: 'var(--fg-secondary)' }} />
                <span className="not-configured">No email templates. Click "Re-seed from Markdown" to import.</span>
              </div>
            )}
          </>
        )}
      </div>
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Template Row
// ---------------------------------------------------------------------------

function TemplateRow({
  template: t,
  expanded,
  onToggleExpand,
  onFieldChange,
  onRoleChange,
}: {
  template: EmailTemplateDef
  expanded: boolean
  onToggleExpand: () => void
  onFieldChange: (key: string, field: string, value: string) => void
  onRoleChange: (key: string, role: RecipientRole) => void
}) {
  return (
    <div style={{ borderBottom: '1px solid var(--border)' }}>
      {/* Summary row */}
      <div
        onClick={onToggleExpand}
        style={{
          display: 'grid',
          gridTemplateColumns: '50px 1fr 120px 80px 24px',
          gap: '8px',
          padding: '6px 12px',
          alignItems: 'center',
          cursor: 'pointer',
          fontSize: '12px',
          fontFamily: 'var(--font-sans)',
        }}
        className="hover:bg-ws-row-expanded-bg"
      >
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--fg-secondary)', fontSize: '11px' }}>
          {t.key}
        </span>
        <span style={{ color: 'var(--fg)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {t.title}
        </span>
        <span style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {t.maps_to.slice(0, 2).map(id => (
            <span key={id} style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--fg-disabled)', background: 'var(--bg-surface)', padding: '0 4px', borderRadius: '2px' }}>
              {id}
            </span>
          ))}
          {t.maps_to.length > 2 && (
            <span style={{ fontSize: '10px', color: 'var(--fg-disabled)' }}>+{t.maps_to.length - 2}</span>
          )}
        </span>
        <Badge variant={ROLE_VARIANTS[t.recipient_role] ?? 'neutral'} size="xs">
          {ROLE_LABELS[t.recipient_role] ?? t.recipient_role}
        </Badge>
        <ChevronDown
          size={14}
          className={clsx('transition-transform', !expanded && '-rotate-90')}
          style={{ color: 'var(--fg-disabled)' }}
        />
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div style={{ padding: '12px 12px 16px 62px', background: 'var(--bg)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* Recipient role */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)', width: '60px' }}>Recipient</span>
            <select
              value={t.recipient_role}
              onChange={e => onRoleChange(t.key, e.target.value as RecipientRole)}
              style={{ fontFamily: 'var(--font-sans)', fontSize: '12px', padding: '2px 6px', border: '1px solid var(--border)', borderRadius: '2px', background: 'var(--bg)' }}
            >
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {/* Subject line */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <span style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)', width: '60px', paddingTop: '4px' }}>Subject</span>
            <input
              type="text"
              value={t.subject}
              onChange={e => onFieldChange(t.key, 'subject', e.target.value)}
              style={{
                flex: 1, fontFamily: 'Calibri, Verdana, sans-serif', fontSize: '13px',
                padding: '4px 8px', border: '1px solid var(--border)', borderRadius: '2px',
                background: 'var(--bg)',
              }}
            />
          </div>

          {/* Body editor */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <span style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)', width: '60px', paddingTop: '4px' }}>Body</span>
            <RichBodyEditor
              html={t.body_html}
              onChange={html => onFieldChange(t.key, 'body_html', html)}
            />
          </div>

          {/* Merge fields */}
          {t.merge_fields.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)', width: '60px' }}>Fields</span>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {t.merge_fields.map(f => (
                  <span key={f} style={{
                    fontFamily: 'var(--font-mono)', fontSize: '10px',
                    padding: '1px 6px', borderRadius: '2px',
                    background: 'rgba(63, 92, 110, 0.08)', color: 'var(--accent)',
                  }}>
                    {`{{${f}}}`}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Task links */}
          {t.maps_to.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)', width: '60px' }}>Tasks</span>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {t.maps_to.map(id => (
                  <span key={id} style={{
                    fontFamily: 'var(--font-mono)', fontSize: '10px',
                    padding: '1px 6px', borderRadius: '2px',
                    background: 'var(--bg-surface)', color: 'var(--fg-secondary)',
                    border: '1px solid var(--border)',
                  }}>
                    {id}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Rich Body Editor (contenteditable with Calibri)
// ---------------------------------------------------------------------------

function RichBodyEditor({ html, onChange }: { html: string; onChange: (html: string) => void }) {
  const editorRef = useRef<HTMLDivElement>(null)
  const [font, setFont] = useState('Calibri')
  const isInternalChange = useRef(false)

  // Sync HTML to editor only on initial mount or external changes
  useEffect(() => {
    if (editorRef.current && !isInternalChange.current) {
      editorRef.current.innerHTML = html
    }
    isInternalChange.current = false
  }, [html])

  const handleInput = useCallback(() => {
    if (!editorRef.current) return
    isInternalChange.current = true
    onChange(editorRef.current.innerHTML)
  }, [onChange])

  const execCommand = (cmd: string, value?: string) => {
    document.execCommand(cmd, false, value)
    editorRef.current?.focus()
  }

  return (
    <div style={{ flex: 1, border: '1px solid var(--border)', borderRadius: '2px', background: 'var(--bg)' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '2px', padding: '4px 6px',
        borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)',
      }}>
        <select
          value={font}
          onChange={e => { setFont(e.target.value); execCommand('fontName', e.target.value) }}
          style={{ fontSize: '11px', padding: '1px 4px', border: '1px solid var(--border)', borderRadius: '2px', background: 'var(--bg)' }}
        >
          <option value="Calibri">Calibri</option>
          <option value="Verdana">Verdana</option>
          <option value="Arial">Arial</option>
        </select>
        <span style={{ width: '1px', height: '16px', background: 'var(--border)', margin: '0 4px' }} />
        <ToolbarButton label="B" cmd="bold" style={{ fontWeight: 700 }} />
        <ToolbarButton label="I" cmd="italic" style={{ fontStyle: 'italic' }} />
        <ToolbarButton label="U" cmd="underline" style={{ textDecoration: 'underline' }} />
        <span style={{ width: '1px', height: '16px', background: 'var(--border)', margin: '0 4px' }} />
        <ToolbarButton label="List" cmd="insertUnorderedList" />
        <ToolbarButton label="Link" cmd="createLink" promptValue />
      </div>

      {/* Editable area */}
      <div
        ref={editorRef}
        contentEditable
        onInput={handleInput}
        style={{
          padding: '8px 10px',
          fontFamily: `${font}, Verdana, sans-serif`,
          fontSize: '11pt',
          lineHeight: 1.5,
          minHeight: '120px',
          maxHeight: '300px',
          overflowY: 'auto',
          outline: 'none',
        }}
      />
    </div>
  )
}

function ToolbarButton({ label, cmd, style, promptValue }: {
  label: string
  cmd: string
  style?: React.CSSProperties
  promptValue?: boolean
}) {
  const handleClick = () => {
    if (promptValue) {
      const value = prompt(`Enter URL:`)
      if (value) document.execCommand(cmd, false, value)
    } else {
      document.execCommand(cmd, false)
    }
  }

  return (
    <button
      onMouseDown={e => { e.preventDefault(); handleClick() }}
      style={{
        fontSize: '11px', padding: '1px 6px', border: '1px solid transparent',
        borderRadius: '2px', background: 'transparent', cursor: 'pointer',
        color: 'var(--fg-secondary)', ...style,
      }}
      className="hover:bg-ws-row-expanded-bg"
    >
      {label}
    </button>
  )
}
