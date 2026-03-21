import { useState, useEffect, useCallback, useRef } from 'react'
import { clsx } from 'clsx'
import { Search, ChevronRight, ChevronLeft, ChevronDown, Users, Building2, Mail, Phone, X, UserPlus } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { Card, Badge, Button, Spinner, TextInput, Select, FilterChip } from '@ui/atoms'
import { api } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Contact {
  id: string
  first_name: string
  last_name: string
  full_name: string
  company: string
  job_title: string
  email_primary: string
  email_secondary: string | null
  phone_business: string | null
  phone_mobile: string | null
  category: string
  notes: string | null
  confidence: string
  staleness_label: string
  last_seen: string | null
  source: string
  created_at: string
  updated_at: string
}

interface ContactDetail extends Contact {
  associations: {
    id: string
    contact_id: string
    project_id: string
    role: string
    is_primary: boolean
    notes: string | null
    created_at: string
    contact_name: string
    contact_email: string
    contact_company: string
    project_name: string
  }[]
}

interface CategoryCount {
  category: string
  count: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZE = 50

const STALENESS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'Active', label: 'Active' },
  { value: 'Aging', label: 'Aging' },
  { value: 'Dormant', label: 'Dormant' },
]

const CONFIDENCE_VARIANT: Record<string, 'success' | 'warning' | 'neutral'> = {
  HIGH: 'success',
  MEDIUM: 'warning',
  LOW: 'neutral',
}

const STALENESS_VARIANT: Record<string, 'success' | 'warning' | 'neutral'> = {
  Active: 'success',
  Aging: 'warning',
  Dormant: 'neutral',
}

function formatRole(role: string): string {
  return role.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Contact Detail (expanded row)
// ---------------------------------------------------------------------------

function ContactDetailRow({ contactId, onClose }: { contactId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<ContactDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.contacts.hub.get(contactId)
      .then((d: ContactDetail) => setDetail(d))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [contactId])

  if (loading) {
    return (
      <tr>
        <td colSpan={6} className="px-3 py-4 bg-ws-row-expanded-bg">
          <Spinner size="sm" />
        </td>
      </tr>
    )
  }

  if (!detail) return null

  return (
    <tr>
      <td colSpan={6} className="px-3 py-4 bg-ws-row-expanded-bg">
        <div className="flex flex-col gap-4 max-w-2xl">
          {/* Contact fields */}
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            {detail.job_title && (
              <>
                <span className="text-ws-text-secondary">Title</span>
                <span className="text-ws-fg">{detail.job_title}</span>
              </>
            )}
            {detail.email_secondary && (
              <>
                <span className="text-ws-text-secondary">Email (secondary)</span>
                <span className="text-ws-fg">{detail.email_secondary}</span>
              </>
            )}
            {detail.phone_business && (
              <>
                <span className="text-ws-text-secondary">Phone (business)</span>
                <span className="text-ws-fg">{detail.phone_business}</span>
              </>
            )}
            {detail.phone_mobile && (
              <>
                <span className="text-ws-text-secondary">Phone (mobile)</span>
                <span className="text-ws-fg">{detail.phone_mobile}</span>
              </>
            )}
            <span className="text-ws-text-secondary">Source</span>
            <span className="text-ws-fg">{detail.source}</span>
            {detail.notes && (
              <>
                <span className="text-ws-text-secondary">Notes</span>
                <span className="text-ws-fg">{detail.notes}</span>
              </>
            )}
          </div>

          {/* Project associations */}
          {detail.associations.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide mb-2">
                Project Associations ({detail.associations.length})
              </h4>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ws-text-secondary">
                    <th className="pb-1 font-medium">Project</th>
                    <th className="pb-1 font-medium">Role</th>
                    <th className="pb-1 font-medium">Primary</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.associations.map(a => (
                    <tr key={a.id} className="border-t border-ws-panel-border/50">
                      <td className="py-1.5 text-ws-fg">{a.project_name || a.project_id}</td>
                      <td className="py-1.5 text-ws-fg">{formatRole(a.role)}</td>
                      <td className="py-1.5">{a.is_primary ? 'Yes' : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex gap-2">
            <Button variant="ghost" size="xs" onClick={onClose}>Collapse</Button>
          </div>
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeSearch, setActiveSearch] = useState('')
  const [category, setCategory] = useState('')
  const [staleness, setStaleness] = useState('')
  const [categories, setCategories] = useState<CategoryCount[]>([])
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [totalCount, setTotalCount] = useState<number | null>(null)
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load categories + total count on mount
  useEffect(() => {
    api.contacts.hub.categories().then(setCategories).catch(() => {})
    api.contacts.hub.count().then((r: { count: number }) => setTotalCount(r.count)).catch(() => {})
  }, [])

  // Load contacts when filters change
  const loadContacts = useCallback(() => {
    setLoading(true)
    api.contacts.hub.search({ q: activeSearch, category, staleness, limit: PAGE_SIZE, offset })
      .then((r: { contacts: Contact[]; total: number }) => {
        setContacts(r.contacts)
        setTotal(r.total)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [activeSearch, category, staleness, offset])

  useEffect(() => { loadContacts() }, [loadContacts])

  // Debounced search
  const handleSearchChange = (value: string) => {
    setSearchQuery(value)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => {
      setActiveSearch(value)
      setOffset(0)
    }, 300)
  }

  const clearCategory = () => { setCategory(''); setOffset(0) }
  const clearStaleness = () => { setStaleness(''); setOffset(0) }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <ModuleLayout module="contacts" activePage="contacts">
      <div className="flex flex-col gap-4 max-w-5xl">
        {/* Header */}
        <div className="flex items-baseline gap-3">
          <h1 className="text-lg font-semibold text-ws-fg">Contacts</h1>
          {totalCount !== null && (
            <span className="text-sm text-ws-text-secondary">{totalCount.toLocaleString()} total</span>
          )}
        </div>

        {/* Search + filters */}
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex-1 min-w-[200px] max-w-sm">
            <TextInput
              placeholder="Search name, email, company..."
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              size="sm"
            />
          </div>
          <Select
            data={[{ value: '', label: 'All categories' }, ...categories.map(c => ({ value: c.category, label: `${c.category} (${c.count})` }))]}
            value={category}
            onChange={(v) => { setCategory(v ?? ''); setOffset(0) }}
            size="sm"
          />
          <Select
            data={STALENESS_OPTIONS}
            value={staleness}
            onChange={(v) => { setStaleness(v ?? ''); setOffset(0) }}
            size="sm"
          />
        </div>

        {/* Active filter chips */}
        {(category || staleness) && (
          <div className="flex gap-2 flex-wrap">
            {category && <FilterChip label={category} onRemove={clearCategory} />}
            {staleness && <FilterChip label={staleness} onRemove={clearStaleness} />}
          </div>
        )}

        {/* Table */}
        {loading && contacts.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ws-text-secondary border-b border-ws-panel-border">
                    <th className="pb-2 pr-3 font-medium">Name</th>
                    <th className="pb-2 pr-3 font-medium">Company</th>
                    <th className="pb-2 pr-3 font-medium">Email</th>
                    <th className="pb-2 pr-3 font-medium">Category</th>
                    <th className="pb-2 pr-3 font-medium">Status</th>
                    <th className="pb-2 pr-3 font-medium w-8"></th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((c) => {
                    const isExpanded = expandedId === c.id
                    return (
                      <ContactRow
                        key={c.id}
                        contact={c}
                        isExpanded={isExpanded}
                        onToggle={() => setExpandedId(isExpanded ? null : c.id)}
                      />
                    )
                  })}
                  {contacts.length === 0 && !loading && (
                    <tr>
                      <td colSpan={6} className="py-8 text-sm text-ws-text-secondary text-center">
                        {activeSearch || category || staleness ? 'No contacts match filters' : 'No contacts in hub'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between text-sm text-ws-text-secondary">
                <span>{total.toLocaleString()} results</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="xs"
                    disabled={offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    leftSection={<ChevronLeft className="w-3.5 h-3.5" />}
                  >
                    Prev
                  </Button>
                  <span className="text-xs tabular-nums">{currentPage} / {totalPages}</span>
                  <Button
                    variant="ghost"
                    size="xs"
                    disabled={offset + PAGE_SIZE >= total}
                    onClick={() => setOffset(offset + PAGE_SIZE)}
                    rightSection={<ChevronRight className="w-3.5 h-3.5" />}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Contact Row (extracted for expand/collapse)
// ---------------------------------------------------------------------------

function ContactRow({
  contact: c,
  isExpanded,
  onToggle,
}: {
  contact: Contact
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        className={clsx(
          'border-b border-ws-panel-border/50 cursor-pointer transition-colors',
          isExpanded ? 'bg-ws-row-expanded-bg' : 'hover:bg-ws-row-expanded-bg',
        )}
        onClick={onToggle}
      >
        <td className="py-2 pr-3">
          <span className="text-ws-fg font-medium">{c.full_name || `${c.first_name} ${c.last_name}`.trim()}</span>
        </td>
        <td className="py-2 pr-3 text-ws-text-secondary">{c.company}</td>
        <td className="py-2 pr-3 text-ws-text-secondary">{c.email_primary}</td>
        <td className="py-2 pr-3">
          {c.category && <Badge variant="light" size="xs">{c.category}</Badge>}
        </td>
        <td className="py-2 pr-3">
          <div className="flex gap-1.5">
            <Badge variant={STALENESS_VARIANT[c.staleness_label] ?? 'neutral'} size="xs">{c.staleness_label}</Badge>
            <Badge variant={CONFIDENCE_VARIANT[c.confidence] ?? 'neutral'} size="xs">{c.confidence}</Badge>
          </div>
        </td>
        <td className="py-2 pr-3">
          <ChevronDown className={clsx('w-3.5 h-3.5 text-ws-text-secondary transition-transform', isExpanded && 'rotate-180')} />
        </td>
      </tr>
      {isExpanded && <ContactDetailRow contactId={c.id} onClose={onToggle} />}
    </>
  )
}
