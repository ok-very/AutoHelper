import {
  Inbox, CheckCircle2, Clock, FileText, Calendar, AlertCircle,
  Activity, Send, Hourglass, Hash, Mail
} from 'lucide-react'
import type { MailEmail, TriageBucket, ViewMode, RequestTab } from '../types'

const CURRENT_USER_EMAIL = 'neal@ballardfineart.com'

interface MailSidebarProps {
  activeView: ViewMode
  onViewChange: (view: ViewMode) => void
  activeBucket: TriageBucket | 'ALL'
  onBucketChange: (bucket: TriageBucket | 'ALL') => void
  activeProject: string | null
  onProjectChange: (project: string | null) => void
  requestTab: RequestTab
  onRequestTabChange: (tab: RequestTab) => void
  emails: MailEmail[]
  accounts: string[]
  activeAccount: string | null
  onAccountChange: (account: string | null) => void
}

const BUCKETS = [
  { id: 'ALL' as const, label: 'All Mail', icon: Inbox },
  { id: 'ACTION_REQUIRED' as const, label: 'Action Required', icon: AlertCircle },
  { id: 'APPROVAL_NEEDED' as const, label: 'Needs Approval', icon: CheckCircle2 },
  { id: 'MEETING_SCHEDULE' as const, label: 'Scheduling', icon: Calendar },
  { id: 'INVOICE' as const, label: 'Invoices', icon: FileText },
  { id: 'TASK_ASSIGNMENT' as const, label: 'Task Updates', icon: Activity },
  { id: 'FYI_ONLY' as const, label: 'FYI', icon: Clock },
]

export function MailSidebar({
  activeView, onViewChange,
  activeBucket, onBucketChange,
  activeProject, onProjectChange,
  requestTab, onRequestTabChange,
  emails,
  accounts, activeAccount, onAccountChange,
}: MailSidebarProps) {
  const pendingCount = emails.filter(e =>
    e.sender !== CURRENT_USER_EMAIL &&
    (e.triage?.bucket === 'ACTION_REQUIRED' || e.triage?.bucket === 'APPROVAL_NEEDED')
  ).length

  const projects = Array.from(new Set(emails.map(e => e.projectName).filter(Boolean))) as string[]

  return (
    <aside style={{
      width: 240, background: 'var(--bg-white)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', flexShrink: 0,
      fontFamily: 'var(--font-sans)',
    }}>
      {/* Accounts */}
      {accounts.length > 0 && (
        <div style={{ padding: '12px 16px 0' }}>
          <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--fg-disabled)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '0 8px 6px' }}>
            Accounts
          </div>
          <NavButton active={!activeAccount} onClick={() => onAccountChange(null)} icon={Mail} label="All Accounts" />
          {accounts.map(acc => (
            <NavButton
              key={acc}
              active={activeAccount === acc}
              onClick={() => onAccountChange(acc)}
              icon={Mail}
              label={acc}
              count={emails.filter(e => e.account === acc).length}
            />
          ))}
        </div>
      )}

      {/* View Toggle */}
      <div style={{ padding: '16px 16px 0' }}>
        <div style={{ display: 'flex', background: 'var(--bg-surface)', padding: 3, borderRadius: 6, marginBottom: 16 }}>
          <button
            onClick={() => onViewChange('triage')}
            style={{
              flex: 1, padding: '6px 0', fontSize: '12px', fontWeight: 700, borderRadius: 4,
              border: 'none', cursor: 'pointer', transition: 'all 0.15s',
              background: activeView === 'triage' ? 'var(--bg-white)' : 'transparent',
              color: activeView === 'triage' ? 'var(--accent)' : 'var(--fg-secondary)',
              boxShadow: activeView === 'triage' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
            }}
          >
            Inbox
          </button>
          <button
            onClick={() => onViewChange('requests')}
            style={{
              flex: 1, padding: '6px 0', fontSize: '12px', fontWeight: 700, borderRadius: 4,
              border: 'none', cursor: 'pointer', transition: 'all 0.15s',
              background: activeView === 'requests' ? 'var(--bg-white)' : 'transparent',
              color: activeView === 'requests' ? 'var(--accent)' : 'var(--fg-secondary)',
              boxShadow: activeView === 'requests' ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
            }}
          >
            Requests
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '0 16px 16px' }}>
        {activeView === 'requests' ? (
          <div>
            <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--fg-disabled)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '8px 8px 6px', marginTop: 4 }}>
              Request Status
            </div>
            <NavButton active={requestTab === 'pending'} onClick={() => onRequestTabChange('pending')} icon={Hourglass} label="Pending Action" count={pendingCount} />
            <NavButton active={requestTab === 'received'} onClick={() => onRequestTabChange('received')} icon={Inbox} label="Received" />
            <NavButton active={requestTab === 'sent'} onClick={() => onRequestTabChange('sent')} icon={Send} label="Sent" />
          </div>
        ) : (
          <div>
            <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--fg-disabled)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '8px 8px 6px', marginTop: 4 }}>
              Buckets
            </div>
            {BUCKETS.map(bucket => {
              const count = bucket.id === 'ALL'
                ? emails.filter(e => e.sender !== CURRENT_USER_EMAIL).length
                : emails.filter(e => e.sender !== CURRENT_USER_EMAIL && e.triage?.bucket === bucket.id).length
              return (
                <NavButton
                  key={bucket.id}
                  active={activeBucket === bucket.id}
                  onClick={() => onBucketChange(bucket.id)}
                  icon={bucket.icon}
                  label={bucket.label}
                  count={count}
                />
              )
            })}
          </div>
        )}

        {/* Projects */}
        <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--fg-disabled)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '20px 8px 6px' }}>
          Projects
        </div>
        <NavButton active={!activeProject} onClick={() => onProjectChange(null)} icon={Hash} label="All Projects" />
        {projects.map(project => {
          const count = emails.filter(e => e.projectName === project).length
          return (
            <NavButton
              key={project}
              active={activeProject === project}
              onClick={() => onProjectChange(project)}
              icon={Hash}
              label={project}
              count={count}
            />
          )
        })}
      </nav>
    </aside>
  )
}

function NavButton({ active, onClick, icon: Icon, label, count }: {
  active: boolean
  onClick: () => void
  icon: typeof Inbox
  label: string
  count?: number
}) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '7px 10px', borderRadius: 4, border: 'none', cursor: 'pointer',
        transition: 'background 0.1s', fontSize: '13px', fontFamily: 'var(--font-sans)',
        background: active ? 'rgba(63, 92, 110, 0.08)' : 'transparent',
        color: active ? 'var(--accent)' : 'var(--fg-secondary)',
      }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Icon size={16} style={{ opacity: active ? 1 : 0.6 }} />
        <span style={{ fontWeight: 500 }}>{label}</span>
      </span>
      {count !== undefined && count > 0 && (
        <span style={{ fontSize: '11px', opacity: 0.6 }}>{count}</span>
      )}
    </button>
  )
}
