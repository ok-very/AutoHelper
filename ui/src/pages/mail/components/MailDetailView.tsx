import { useState, useEffect, useCallback } from 'react'
import {
  User, Tag, AlertCircle, CheckCircle2,
  ArrowUpRight, MessageSquare, Mail, Layers, Loader2, FolderUp, Copy,
  UserPlus, BookUser
} from 'lucide-react'
import type { MailEmail } from '../types'
import { MailAttachmentTable } from './MailAttachmentTable'
import { ProjectContext } from './ProjectContext'
import { api } from '@/lib/api'

// Grouped slot picker — mirrors CONTACT_SLOTS in hub.py
const SLOT_GROUPS = [
  { label: 'Team', slots: [
    { value: 'contact', label: 'Contact' },
    { value: 'owner', label: 'Owner' },
    { value: 'architect', label: 'Architect' },
    { value: 'landscape', label: 'Landscape' },
  ]},
  { label: 'Stages', slots: [
    { value: 'ppap', label: 'PPAP' },
    { value: 'dpap', label: 'DPAP' },
    { value: 'eoi', label: 'EOI' },
  ]},
  { label: 'Selection', slots: [
    { value: 'sp1', label: 'SP#1' },
    { value: 'ao', label: 'AO' },
    { value: 'sp2', label: 'SP#2' },
    { value: 'selection_panel', label: 'Selection Panel' },
  ]},
  { label: 'Artists', slots: [
    { value: 'shortlisted_artist', label: 'Shortlisted Artist' },
    { value: 'selected_artist', label: 'Selected Artist' },
  ]},
  { label: 'Advisory', slots: [
    { value: 'community_advisory', label: 'Community Advisory' },
    { value: 'indigenous_advisor', label: 'Indigenous Advisor' },
  ]},
  { label: 'Other', slots: [
    { value: 'project_coordinator', label: 'Project Coordinator' },
    { value: 'engineer', label: 'Engineer' },
    { value: 'city_planner', label: 'City Planner' },
    { value: 'other', label: 'Other' },
  ]},
] as { label: string; slots: { value: string; label: string }[] }[]

const SINGULAR_SLOTS = new Set([
  'contact', 'owner', 'architect', 'landscape',
  'ppap', 'dpap', 'eoi', 'ao',
  'selected_artist', 'project_coordinator', 'engineer', 'city_planner',
])

const SLOT_TO_MERGE: Record<string, string> = {
  contact: '{{developer_contact_name}}',
  city_planner: '{{city_planner_name}}',
  architect: '{{architect_name}}',
  landscape: '{{landscape_architect_name}}',
  selected_artist: '{{artist_name}}',
  project_coordinator: '{{coordinator_name}}',
  engineer: '{{engineer_name}}',
}

function splitName(full: string): { first: string; last: string } {
  const parts = full.trim().split(/\s+/)
  if (parts.length <= 1) return { first: parts[0] || '', last: '' }
  return { first: parts[0], last: parts.slice(1).join(' ') }
}

function domainFromEmail(email: string): string {
  const domain = email.split('@')[1] || ''
  // Strip common freemail domains — not useful as company
  const freemail = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com', 'aol.com']
  if (freemail.includes(domain.toLowerCase())) return ''
  return domain
}

interface ContactFormData {
  email_primary: string
  full_name: string
  first_name: string
  last_name: string
  company: string
}

interface MailDetailViewProps {
  email: MailEmail | null
}

export function MailDetailView({ email }: MailDetailViewProps) {
  const [checkedActions, setCheckedActions] = useState<Set<number>>(new Set())
  const [generatedDraft, setGeneratedDraft] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedAttachments, setSelectedAttachments] = useState<Set<string>>(new Set())
  const [draftFeedback, setDraftFeedback] = useState('')

  // Contact resolution state
  const [senderStatus, setSenderStatus] = useState<'loading' | 'known' | 'unknown' | null>(null)
  const [resolvedContact, setResolvedContact] = useState<any>(null)
  const [showContactForm, setShowContactForm] = useState(false)
  const [contactForm, setContactForm] = useState<ContactFormData>({ email_primary: '', full_name: '', first_name: '', last_name: '', company: '' })
  const [isSavingContact, setIsSavingContact] = useState(false)
  const [contactFeedback, setContactFeedback] = useState('')
  const [createdContactId, setCreatedContactId] = useState<string | null>(null)
  const [associateSlot, setAssociateSlot] = useState('other')
  const [existingContacts, setExistingContacts] = useState<any[]>([])
  const [slotConflict, setSlotConflict] = useState<string | null>(null)
  const [associationDone, setAssociationDone] = useState(false)
  const [isPushingClickup, setIsPushingClickup] = useState(false)
  const [clickupPushResult, setClickupPushResult] = useState<string | null>(null)

  useEffect(() => {
    if (email) {
      setGeneratedDraft('')
      setCheckedActions(new Set())
      setSelectedAttachments(new Set())
      setDraftFeedback('')
      // Reset contact state
      setShowContactForm(false)
      setContactFeedback('')
      setCreatedContactId(null)
      setAssociationDone(false)
      setClickupPushResult(null)
      setSlotConflict(null)
      setExistingContacts([])
      // Resolve sender
      if (email.sender) {
        setSenderStatus('loading')
        setResolvedContact(null)
        api.contacts.resolveSender(email.sender).then(result => {
          if (result && result.contact_id) {
            setSenderStatus('known')
            setResolvedContact(result)
          } else {
            setSenderStatus('unknown')
          }
        }).catch(() => {
          setSenderStatus('unknown')
        })
      } else {
        setSenderStatus(null)
      }
    }
  }, [email?.id])

  const toggleAction = useCallback((index: number) => {
    setCheckedActions(prev => {
      const next = new Set(prev)
      next.has(index) ? next.delete(index) : next.add(index)
      return next
    })
  }, [])

  const handleOpenContactForm = useCallback(() => {
    if (!email) return
    const name = email.fromName || ''
    const { first, last } = splitName(name)
    setContactForm({
      email_primary: email.sender || '',
      full_name: name,
      first_name: first,
      last_name: last,
      company: domainFromEmail(email.sender || ''),
    })
    setShowContactForm(true)
    setContactFeedback('')
    setCreatedContactId(null)
  }, [email])

  const handleSaveContact = async () => {
    if (!contactForm.email_primary) return
    setIsSavingContact(true)
    setContactFeedback('')
    try {
      const result = await api.contacts.hub.create({
        email_primary: contactForm.email_primary,
        full_name: contactForm.full_name,
        first_name: contactForm.first_name,
        last_name: contactForm.last_name,
        company: contactForm.company,
        source: 'mail_triage',
      })
      const id = result.contact_id || result.id
      setCreatedContactId(id)
      setSenderStatus('known')
      setContactFeedback('Contact saved')
    } catch {
      setContactFeedback('Failed to save contact')
    } finally {
      setIsSavingContact(false)
    }
  }

  const handleSlotChange = useCallback(async (slot: string) => {
    setAssociateSlot(slot)
    setSlotConflict(null)
    if (!email?.project_id || !SINGULAR_SLOTS.has(slot)) return
    // Check for existing contact in this slot
    try {
      const contacts = existingContacts.length
        ? existingContacts
        : await api.contacts.projectContacts(email.project_id).then(c => { setExistingContacts(c); return c })
      const occupant = contacts.find((a: any) => a.role === slot)
      if (occupant) {
        setSlotConflict(`${occupant.contact_name || occupant.contact_email} is already ${SLOT_GROUPS.flatMap(g => g.slots).find(s => s.value === slot)?.label || slot}`)
      }
    } catch { /* ignore */ }
  }, [email?.project_id, existingContacts])

  const handleAssociateProject = async () => {
    if (!createdContactId || !email?.project_id) return
    try {
      await api.contacts.associateContact(email.project_id, createdContactId, associateSlot)
      setAssociationDone(true)
      setSlotConflict(null)
      const mergeField = SLOT_TO_MERGE[associateSlot]
      const slotLabel = SLOT_GROUPS.flatMap(g => g.slots).find(s => s.value === associateSlot)?.label || associateSlot
      setContactFeedback(
        `Linked as ${slotLabel}` + (mergeField ? ` — fills ${mergeField} in templates` : '')
      )
    } catch {
      setContactFeedback('Saved but failed to link to project')
    }
  }

  const handlePushToClickup = async () => {
    if (!email?.project_id) return
    setIsPushingClickup(true)
    setClickupPushResult(null)
    try {
      const result = await api.bfaTodo.pushContactsToClickup(email.project_id)
      if (result.error) {
        setClickupPushResult(result.error)
      } else if (result.pushed?.length) {
        setClickupPushResult(`Pushed: ${result.pushed.join(', ')}`)
      } else {
        setClickupPushResult('No mapped fields to push (staged in hub)')
      }
    } catch {
      setClickupPushResult('Push failed')
    } finally {
      setIsPushingClickup(false)
    }
  }

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
                {senderStatus === 'known' && (
                  <span style={{
                    padding: '2px 8px', fontSize: '10px', fontWeight: 700,
                    color: 'var(--color-success)', border: '1px solid var(--color-success)',
                    borderRadius: 10, display: 'flex', alignItems: 'center', gap: 4,
                  }}>
                    <BookUser size={10} /> In Contacts
                  </span>
                )}
                {senderStatus === 'unknown' && !showContactForm && (
                  <button
                    onClick={handleOpenContactForm}
                    style={{
                      padding: '2px 8px', fontSize: '10px', fontWeight: 700,
                      color: 'var(--accent)', background: 'transparent',
                      border: '1px solid var(--accent)', borderRadius: 10,
                      cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
                    }}
                  >
                    <UserPlus size={10} /> Add to Contacts
                  </button>
                )}
                {senderStatus === 'loading' && (
                  <Loader2 size={12} className="animate-spin" style={{ color: 'var(--fg-disabled)' }} />
                )}
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

          {/* Add to Contacts — inline form */}
          {showContactForm && (
            <div style={{ padding: 24, borderBottom: '1px solid var(--bg-surface)', background: 'var(--bg)' }}>
              <h4 style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--fg-disabled)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                <UserPlus size={14} /> New Contact
              </h4>

              {!createdContactId ? (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                    {(['first_name', 'last_name', 'email_primary', 'company'] as const).map(field => (
                      <label key={field} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--fg-disabled)', textTransform: 'uppercase' }}>
                          {field.replace(/_/g, ' ')}
                        </span>
                        <input
                          value={contactForm[field]}
                          onChange={e => setContactForm(f => ({ ...f, [field]: e.target.value }))}
                          style={{
                            padding: '6px 8px', fontSize: '13px', border: '1px solid var(--border)',
                            borderRadius: 4, background: 'var(--bg-white)', color: 'var(--fg)',
                            outline: 'none',
                          }}
                        />
                      </label>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <button
                      onClick={handleSaveContact}
                      disabled={isSavingContact || !contactForm.email_primary}
                      style={{
                        padding: '6px 14px', fontSize: '12px', fontWeight: 700,
                        background: 'var(--accent)', color: 'var(--accent-fg)',
                        border: 'none', borderRadius: 4, cursor: 'pointer',
                        opacity: isSavingContact ? 0.6 : 1,
                      }}
                    >
                      {isSavingContact ? 'Saving...' : 'Save Contact'}
                    </button>
                    <button
                      onClick={() => setShowContactForm(false)}
                      style={{
                        padding: '6px 14px', fontSize: '12px', fontWeight: 600,
                        background: 'transparent', color: 'var(--fg-secondary)',
                        border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                    {contactFeedback && (
                      <span style={{ fontSize: '12px', color: contactFeedback.includes('Failed') ? 'var(--color-error)' : 'var(--color-success)' }}>
                        {contactFeedback}
                      </span>
                    )}
                  </div>
                </>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <span style={{ fontSize: '12px', color: 'var(--color-success)', fontWeight: 600 }}>
                    {contactFeedback}
                  </span>

                  {/* Association step — slot picker + conflict check */}
                  {email.project_id && !associationDone && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: '12px', color: 'var(--fg-secondary)' }}>
                          Link to {email.projectName || email.project_id} as:
                        </span>
                        <select
                          value={associateSlot}
                          onChange={e => handleSlotChange(e.target.value)}
                          style={{
                            padding: '4px 8px', fontSize: '12px', border: '1px solid var(--border)',
                            borderRadius: 4, background: 'var(--bg-white)', color: 'var(--fg)',
                          }}
                        >
                          {SLOT_GROUPS.map(group => (
                            <optgroup key={group.label} label={group.label}>
                              {group.slots.map(s => (
                                <option key={s.value} value={s.value}>{s.label}</option>
                              ))}
                            </optgroup>
                          ))}
                        </select>
                        <button
                          onClick={handleAssociateProject}
                          style={{
                            padding: '4px 12px', fontSize: '12px', fontWeight: 700,
                            background: 'var(--accent)', color: 'var(--accent-fg)',
                            border: 'none', borderRadius: 4, cursor: 'pointer',
                          }}
                        >
                          Link
                        </button>
                        <button
                          onClick={() => setShowContactForm(false)}
                          style={{
                            padding: '4px 12px', fontSize: '12px', fontWeight: 600,
                            background: 'transparent', color: 'var(--fg-secondary)',
                            border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer',
                          }}
                        >
                          Skip
                        </button>
                      </div>
                      {slotConflict && (
                        <span style={{ fontSize: '11px', color: 'var(--color-warning, #b45309)' }}>
                          {slotConflict} — linking will replace
                        </span>
                      )}
                      {SLOT_TO_MERGE[associateSlot] && (
                        <span style={{ fontSize: '11px', color: 'var(--fg-disabled)' }}>
                          Fills {SLOT_TO_MERGE[associateSlot]} in email templates
                        </span>
                      )}
                    </div>
                  )}

                  {/* Post-association: ClickUp push + done */}
                  {associationDone && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      {email.project_id && (
                        <button
                          onClick={handlePushToClickup}
                          disabled={isPushingClickup}
                          style={{
                            padding: '4px 12px', fontSize: '12px', fontWeight: 700,
                            background: 'var(--bg-white)', color: 'var(--fg)',
                            border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer',
                            opacity: isPushingClickup ? 0.6 : 1,
                          }}
                        >
                          {isPushingClickup ? 'Pushing...' : 'Push to ClickUp'}
                        </button>
                      )}
                      <button
                        onClick={() => setShowContactForm(false)}
                        style={{
                          padding: '4px 12px', fontSize: '12px', fontWeight: 600,
                          background: 'transparent', color: 'var(--fg-secondary)',
                          border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer',
                        }}
                      >
                        Done
                      </button>
                      {clickupPushResult && (
                        <span style={{ fontSize: '11px', color: clickupPushResult.includes('fail') || clickupPushResult.includes('error') ? 'var(--color-error)' : 'var(--color-success)' }}>
                          {clickupPushResult}
                        </span>
                      )}
                    </div>
                  )}

                  {/* No project — just done */}
                  {!email.project_id && !associationDone && (
                    <button
                      onClick={() => setShowContactForm(false)}
                      style={{
                        padding: '4px 12px', fontSize: '12px', fontWeight: 600, alignSelf: 'flex-start',
                        background: 'transparent', color: 'var(--fg-secondary)',
                        border: '1px solid var(--border)', borderRadius: 4, cursor: 'pointer',
                      }}
                    >
                      Done
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

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
