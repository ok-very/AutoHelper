import { useState, useEffect, useCallback } from 'react'
import {
  User, Tag, AlertCircle, CheckCircle2,
  ArrowUpRight, MessageSquare, Mail, Layers, Loader2, FolderUp, Copy
} from 'lucide-react'
import type { MailEmail } from '../types'
import { MailAttachmentTable } from './MailAttachmentTable'
import { ProjectContext } from './ProjectContext'

interface MailDetailViewProps {
  email: MailEmail | null
}

export function MailDetailView({ email }: MailDetailViewProps) {
  const [checkedActions, setCheckedActions] = useState<Set<number>>(new Set())
  const [generatedDraft, setGeneratedDraft] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedAttachments, setSelectedAttachments] = useState<Set<string>>(new Set())
  const [draftFeedback, setDraftFeedback] = useState('')

  useEffect(() => {
    if (email) {
      setGeneratedDraft('')
      setCheckedActions(new Set())
      setSelectedAttachments(new Set())
      setDraftFeedback('')
    }
  }, [email?.id])

  const toggleAction = useCallback((index: number) => {
    setCheckedActions(prev => {
      const next = new Set(prev)
      next.has(index) ? next.delete(index) : next.add(index)
      return next
    })
  }, [])

  const handleGenerateDraft = async () => {
    if (!email) return
    setIsGenerating(true)
    try {
      const response = await fetch('/mail/draft/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email_id: email.id,
          subject: email.subject,
          sender: email.sender,
          sender_name: email.fromName,
          project: email.projectName || email.project_id,
          body_text: email.body_preview || '',
        })
      })
      if (!response.ok) throw new Error('API error')
      const result = await response.json()
      setGeneratedDraft(result.draft || result.html_body || 'Failed to generate draft')
    } catch {
      // Fallback to local template
      setGeneratedDraft(
        `Hi ${email.fromName?.split(' ')[0] || 'there'},\n\n` +
        `Thank you for your email regarding ${email.projectName || 'the project'}.\n\n` +
        `I'll review this and get back to you shortly.\n\nBest regards,\nNeal`
      )
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSendToOutlook = async () => {
    if (!email || !generatedDraft) return
    setDraftFeedback('')
    try {
      const response = await fetch('/mail/draft/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: email.sender || '',
          subject: email.subject || '',
          body: generatedDraft,
        })
      })
      const result = await response.json()
      if (result.ok) {
        setDraftFeedback('Draft created in Outlook')
      } else {
        setDraftFeedback(result.error || 'Failed to create draft')
      }
    } catch {
      setDraftFeedback('Failed to connect to mail service')
    }
  }

  const handleCopyToClipboard = () => {
    if (generatedDraft) {
      navigator.clipboard.writeText(generatedDraft).then(() => {
        setDraftFeedback('Copied to clipboard')
        setTimeout(() => setDraftFeedback(''), 2000)
      })
    }
  }

  if (!email) {
    return (
      <section style={{ flex: 1, background: 'var(--bg)', overflow: 'auto', padding: 32 }}>
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--fg-disabled)', gap: 16 }}>
          <Mail size={64} style={{ opacity: 0.2 }} />
          <p style={{ fontWeight: 500, fontFamily: 'var(--font-sans)' }}>Select an email to view details</p>
        </div>
      </section>
    )
  }

  const triage = email.triage
  const allPreReplyComplete = triage
    ? triage.preReplyActions.every((_, i) => checkedActions.has(i))
    : true

  return (
    <section style={{ flex: 1, background: 'var(--bg)', overflow: 'auto', padding: 32, fontFamily: 'var(--font-sans)' }}>
      <div style={{ maxWidth: 800, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>

        {/* Header Card */}
        <div style={{ background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 4, overflow: 'hidden' }}>
          {/* Email Meta */}
          <div style={{ padding: 24, borderBottom: '1px solid var(--bg-surface)', background: 'var(--bg)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--fg)', marginBottom: 8 }}>{email.subject}</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: '13px', color: 'var(--fg-secondary)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <User size={14} style={{ color: 'var(--fg-disabled)' }} />
                <span style={{ fontWeight: 600, color: 'var(--fg)' }}>{email.fromName}</span>
                <span style={{ color: 'var(--fg-disabled)' }}>&lt;{email.sender}&gt;</span>
              </span>
              <span style={{ color: 'var(--fg-disabled)' }}>&middot;</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Tag size={14} style={{ color: 'var(--fg-disabled)' }} />
                {email.projectName || email.project_id}
              </span>
            </div>

            {/* Classification badges */}
            {triage && (
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginTop: 12 }}>
                <span style={{
                  padding: '4px 12px', background: 'var(--bg-white)', border: '1px solid var(--border)',
                  borderRadius: 16, fontSize: '11px', fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)' }} />
                  {triage.bucket.replace(/_/g, ' ')}
                </span>
                <span style={{
                  padding: '4px 12px', background: 'var(--bg-white)', border: '1px solid var(--border)',
                  borderRadius: 16, fontSize: '11px', fontWeight: 600,
                }}>
                  Confidence: {Math.round(triage.confidence * 100)}%
                </span>
              </div>
            )}
          </div>

          {/* Project Context — stage, templates, task linking */}
          <ProjectContext email={email} />

          {/* Triage Intelligence */}
          {triage && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', borderBottom: '1px solid var(--bg-surface)' }}>
              {/* Reasoning */}
              <div style={{ padding: 24, borderRight: '1px solid var(--bg-surface)' }}>
                <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-disabled)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                  <AlertCircle size={14} /> Reasoning
                </h4>
                <ul style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {triage.reasoning.map((r, i) => (
                    <li key={i} style={{ fontSize: '12px', color: 'var(--fg-secondary)', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                      <span style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--border)', marginTop: 6, flexShrink: 0 }} />
                      {r}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Pre-Reply Actions */}
              <div style={{ padding: 24, background: 'var(--bg)' }}>
                <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-disabled)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                  <CheckCircle2 size={14} /> Before Responding
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {triage.preReplyActions.length > 0 ? triage.preReplyActions.map((action, i) => (
                    <div
                      key={i}
                      onClick={() => toggleAction(i)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: 12, background: 'var(--bg-white)', border: '1px solid var(--border)',
                        borderRadius: 4, cursor: 'pointer', transition: 'border-color 0.1s',
                        borderColor: checkedActions.has(i) ? 'var(--color-success)' : 'var(--border)',
                      }}
                    >
                      <div style={{
                        width: 20, height: 20, borderRadius: 4, border: '2px solid',
                        borderColor: checkedActions.has(i) ? 'var(--color-success)' : 'var(--border)',
                        background: checkedActions.has(i) ? 'var(--color-success)' : 'transparent',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                      }}>
                        {checkedActions.has(i) && <CheckCircle2 size={12} style={{ color: 'white' }} />}
                      </div>
                      <div style={{ flex: 1 }}>
                        <p style={{
                          fontSize: '13px', fontWeight: 500,
                          color: checkedActions.has(i) ? 'var(--fg-secondary)' : 'var(--fg)',
                          textDecoration: checkedActions.has(i) ? 'line-through' : 'none',
                        }}>
                          {action.description}
                        </p>
                        <span style={{ fontSize: '10px', color: 'var(--fg-disabled)', textTransform: 'uppercase', fontWeight: 700 }}>
                          {action.type}
                        </span>
                      </div>
                      <ArrowUpRight size={14} style={{ color: 'var(--fg-disabled)' }} />
                    </div>
                  )) : (
                    <p style={{ fontSize: '13px', color: 'var(--fg-disabled)', fontStyle: 'italic' }}>
                      No specific pre-reply actions detected.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Email Body */}
          <div style={{ padding: 32, background: 'var(--bg-white)', minHeight: 150, lineHeight: 1.6 }}>
            <p style={{ whiteSpace: 'pre-line', color: 'var(--fg-secondary)', fontSize: '14px' }}>
              {email.body_preview || 'No preview available'}
            </p>
          </div>

          {/* Attachments */}
          {email.attachments && email.attachments.length > 0 && (
            <div style={{ padding: '0 32px 24px' }}>
              <MailAttachmentTable
                attachments={email.attachments}
                selectedIds={selectedAttachments}
                onSelectionChange={setSelectedAttachments}
              />
            </div>
          )}

          {/* Reply Composer */}
          <div style={{ padding: 24, background: 'var(--bg)', borderTop: '1px solid var(--bg-surface)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <MessageSquare size={16} style={{ color: 'var(--accent)' }} />
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--fg)' }}>Draft Reply</span>
              </div>
              <button
                onClick={handleGenerateDraft}
                disabled={isGenerating}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 12px', background: 'var(--accent)', color: 'var(--accent-fg)',
                  border: 'none', borderRadius: 4, fontSize: '12px', fontWeight: 700,
                  cursor: 'pointer', opacity: isGenerating ? 0.6 : 1,
                }}
              >
                {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <MessageSquare size={14} />}
                {isGenerating ? 'Generating...' : 'Generate Draft'}
              </button>
            </div>

            {generatedDraft ? (
              <div style={{ padding: 16, background: 'var(--bg-white)', border: '1px solid var(--border)', borderRadius: 4, marginBottom: 12 }}>
                <textarea
                  value={generatedDraft}
                  onChange={(e) => setGeneratedDraft(e.target.value)}
                  style={{
                    width: '100%', fontSize: '13px', color: 'var(--fg)', minHeight: 120,
                    resize: 'vertical', outline: 'none', border: 'none', background: 'transparent',
                    fontFamily: 'Calibri, Verdana, sans-serif', lineHeight: 1.5,
                  }}
                />
              </div>
            ) : triage?.suggestedReplyOpener ? (
              <div style={{
                padding: 16, background: 'var(--bg-white)', border: '1px solid var(--border)',
                borderRadius: 4, fontSize: '13px', color: 'var(--fg-secondary)', fontStyle: 'italic',
                marginBottom: 12,
              }}>
                "{triage.suggestedReplyOpener}"
              </div>
            ) : (
              <p style={{ fontSize: '12px', color: 'var(--fg-disabled)', fontStyle: 'italic', marginBottom: 12 }}>
                Click "Generate Draft" to create a reply.
              </p>
            )}

            <div style={{ display: 'flex', gap: 12 }}>
              <button
                onClick={handleSendToOutlook}
                disabled={!generatedDraft}
                style={{
                  flex: 1, padding: '10px 0', background: 'var(--accent)', color: 'var(--accent-fg)',
                  border: 'none', borderRadius: 4, fontWeight: 700, fontSize: '13px',
                  cursor: generatedDraft ? 'pointer' : 'not-allowed',
                  opacity: generatedDraft ? 1 : 0.5,
                }}
              >
                Send to Outlook Drafts
              </button>
              <button
                onClick={handleCopyToClipboard}
                disabled={!generatedDraft}
                style={{
                  padding: '10px 16px', background: 'var(--bg-white)', border: '1px solid var(--border)',
                  borderRadius: 4, fontWeight: 700, fontSize: '13px', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6, color: 'var(--fg-secondary)',
                  opacity: generatedDraft ? 1 : 0.5,
                }}
              >
                <Copy size={14} /> Copy
              </button>
            </div>

            {draftFeedback && (
              <p style={{ marginTop: 8, fontSize: '12px', color: 'var(--color-success)' }}>
                {draftFeedback}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
