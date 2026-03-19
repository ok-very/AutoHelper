import { useState, useEffect, useMemo } from 'react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { useMailInbox } from './hooks/useMailInbox'
import { MailSidebar } from './components/MailSidebar'
import { MailEmailList } from './components/MailEmailList'
import { MailDetailView } from './components/MailDetailView'
import type { ViewMode, RequestTab, TriageBucket } from './types'

const CURRENT_USER_EMAIL = 'neal@ballardfineart.com'

export function MailPage() {
  // Account state
  const [accounts, setAccounts] = useState<string[]>([])
  const [activeAccount, setActiveAccount] = useState<string | null>(null)

  // Fetch accounts on mount
  useEffect(() => {
    fetch('/mail/accounts')
      .then(r => r.ok ? r.json() : [])
      .then(setAccounts)
      .catch(() => {})
  }, [])

  // Inbox — filtered by account
  const { emails, loading } = useMailInbox({
    account: activeAccount ?? undefined,
  })
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // View state
  const [activeView, setActiveView] = useState<ViewMode>('triage')
  const [activeBucket, setActiveBucket] = useState<TriageBucket | 'ALL'>('ALL')
  const [activeProject, setActiveProject] = useState<string | null>(null)
  const [requestTab, setRequestTab] = useState<RequestTab>('pending')
  const [searchQuery, setSearchQuery] = useState('')

  // Filter and sort emails
  const filteredEmails = useMemo(() => {
    let filtered = emails

    if (activeView === 'requests') {
      if (requestTab === 'received') {
        filtered = filtered.filter(e => e.sender !== CURRENT_USER_EMAIL)
      } else if (requestTab === 'sent') {
        filtered = filtered.filter(e => e.sender === CURRENT_USER_EMAIL)
      } else if (requestTab === 'pending') {
        filtered = filtered.filter(e =>
          e.sender !== CURRENT_USER_EMAIL &&
          (e.triage?.bucket === 'ACTION_REQUIRED' || e.triage?.bucket === 'APPROVAL_NEEDED')
        )
      }
    } else {
      filtered = filtered.filter(e => e.sender !== CURRENT_USER_EMAIL)
      if (activeBucket !== 'ALL') {
        filtered = filtered.filter(e => e.triage?.bucket === activeBucket)
      }
      if (activeProject) {
        filtered = filtered.filter(e => e.projectName === activeProject)
      }
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(e =>
        (e.subject?.toLowerCase().includes(query)) ||
        (e.fromName?.toLowerCase().includes(query)) ||
        (e.projectName?.toLowerCase().includes(query))
      )
    }

    return filtered.sort((a, b) => {
      if (activeView === 'requests') {
        return new Date(b.received_at || 0).getTime() - new Date(a.received_at || 0).getTime()
      }
      return (b.priority ?? 2) - (a.priority ?? 2)
    })
  }, [emails, activeView, activeBucket, activeProject, requestTab, searchQuery])

  const selectedEmail = useMemo(
    () => emails.find(e => e.id === selectedId) || null,
    [emails, selectedId]
  )

  return (
    <ModuleLayout module="mail" activePage="inbox" flush>
      <div style={{ display: 'flex', height: '100%', overflow: 'hidden', fontFamily: 'var(--font-sans)' }}>
        <MailSidebar
          activeView={activeView}
          onViewChange={setActiveView}
          activeBucket={activeBucket}
          onBucketChange={setActiveBucket}
          activeProject={activeProject}
          onProjectChange={setActiveProject}
          requestTab={requestTab}
          onRequestTabChange={setRequestTab}
          emails={emails}
          accounts={accounts}
          activeAccount={activeAccount}
          onAccountChange={setActiveAccount}
        />
        <MailEmailList
          emails={filteredEmails}
          selectedId={selectedId}
          onSelectEmail={(email) => setSelectedId(email.id)}
          activeView={activeView}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />
        <MailDetailView email={selectedEmail} />
      </div>
    </ModuleLayout>
  )
}
