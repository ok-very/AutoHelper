import {
  Search, Paperclip, Mail,
  Inbox, CheckCircle2, Clock, FileText, Calendar, AlertCircle, Activity
} from 'lucide-react'
import type { MailEmail, TriageBucket, ViewMode } from '../types'
import { DecayMeter } from './DecayMeter'

interface MailEmailListProps {
  emails: MailEmail[]
  selectedId: string | null
  onSelectEmail: (email: MailEmail) => void
  activeView: ViewMode
  searchQuery: string
  onSearchChange: (query: string) => void
}

const BUCKET_ICONS: Record<string, typeof Mail> = {
  ALL: Inbox,
  ACTION_REQUIRED: AlertCircle,
  APPROVAL_NEEDED: CheckCircle2,
  MEETING_SCHEDULE: Calendar,
  INVOICE: FileText,
  TASK_ASSIGNMENT: Activity,
  AWAITING_REPLY: Clock,
  FYI_ONLY: Clock,
}

export function MailEmailList({
  emails, selectedId, onSelectEmail, activeView, searchQuery, onSearchChange,
}: MailEmailListProps) {
  return (
    <div style={{
      width: 420, background: 'var(--bg-white)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
      fontFamily: 'var(--font-sans)',
    }}>
      {/* Search */}
      <div style={{ padding: 16, borderBottom: '1px solid var(--border)', position: 'sticky', top: 0, zIndex: 10, background: 'var(--bg-white)' }}>
        <div style={{ position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-disabled)' }} />
          <input
            type="text"
            placeholder={activeView === 'requests' ? 'Search requests...' : 'Search triage...'}
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            style={{
              width: '100%', paddingLeft: 40, paddingRight: 16, paddingTop: 8, paddingBottom: 8,
              background: 'var(--bg-surface)', border: '1px solid transparent', borderRadius: 8,
              fontSize: '13px', fontFamily: 'var(--font-sans)', color: 'var(--fg)',
              outline: 'none', transition: 'border 0.15s',
            }}
          />
        </div>
      </div>

      {/* Email List */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {emails.map(email => {
          const BucketIcon = BUCKET_ICONS[email.triage?.bucket || 'FYI_ONLY'] || Mail
          const isSelected = selectedId === email.id

          return (
            <button
              key={email.id}
              onClick={() => onSelectEmail(email)}
              style={{
                width: '100%', textAlign: 'left', padding: 16,
                borderBottom: '1px solid var(--bg-surface)',
                background: isSelected ? 'rgba(63, 92, 110, 0.05)' : 'transparent',
                cursor: 'pointer', position: 'relative', border: 'none',
                fontFamily: 'var(--font-sans)', transition: 'background 0.1s',
              }}
            >
              {/* Selection indicator */}
              {isSelected && (
                <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: 'var(--accent)' }} />
              )}

              {/* Header: Project + Time */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-disabled)' }}>
                  {email.projectName || email.project_id || ''}
                </span>
                <span style={{ fontSize: '10px', color: 'var(--fg-disabled)' }}>
                  {email.received_at ? new Date(email.received_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                </span>
              </div>

              {/* Subject */}
              <h3 style={{
                fontSize: '13px', fontWeight: 600, marginBottom: 4,
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                color: isSelected ? 'var(--accent)' : 'var(--fg)',
              }}>
                {email.subject || '(no subject)'}
              </h3>

              {/* Body preview */}
              <p style={{
                fontSize: '12px', color: 'var(--fg-secondary)',
                display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                overflow: 'hidden', marginBottom: 10, lineHeight: 1.4,
              }}>
                {email.body_preview || ''}
              </p>

              {/* Footer */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {activeView === 'triage' && email.priority && (
                    <span style={{
                      padding: '2px 8px', borderRadius: 3, fontSize: '10px', fontWeight: 700,
                      background: email.priority >= 4 ? 'rgba(140, 74, 74, 0.1)' : 'var(--bg-surface)',
                      color: email.priority >= 4 ? 'var(--color-error)' : 'var(--fg-secondary)',
                    }}>
                      P{email.priority}
                    </span>
                  )}
                  {email.hasAttachments && (
                    <Paperclip size={12} style={{ color: 'var(--fg-disabled)' }} />
                  )}
                </div>

                {activeView === 'requests' && email.received_at ? (
                  <DecayMeter timestamp={email.received_at} />
                ) : (
                  <BucketIcon size={14} style={{ color: 'var(--fg-disabled)' }} />
                )}
              </div>
            </button>
          )
        })}

        {emails.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 192, color: 'var(--fg-disabled)' }}>
            <Mail size={32} style={{ opacity: 0.4, marginBottom: 8 }} />
            <p style={{ fontSize: '13px' }}>No emails match your filters</p>
          </div>
        )}
      </div>
    </div>
  )
}
