import { Search } from 'lucide-react'

interface FilterBarProps {
  searchQuery: string
  onSearchChange: (q: string) => void
  filterPhase: string
  onPhaseChange: (v: string) => void
  filterLead: string
  onLeadChange: (v: string) => void
  filterCity: string
  onCityChange: (v: string) => void
  showOnHold: boolean
  onShowOnHoldChange: (v: boolean) => void
  showIssuesOnly: boolean
  onShowIssuesOnlyChange: (v: boolean) => void
  phases: string[]
  leads: string[]
  cities: string[]
  onHoldCount: number
  issueCount: number
}

export function FilterBar({
  searchQuery, onSearchChange,
  filterPhase, onPhaseChange,
  filterLead, onLeadChange,
  filterCity, onCityChange,
  showOnHold, onShowOnHoldChange,
  showIssuesOnly, onShowIssuesOnlyChange,
  phases, leads, cities,
  onHoldCount, issueCount,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative flex-1 min-w-[200px] max-w-sm">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--fg-disabled)' }} />
        <input
          type="text"
          className="search-input w-full pl-8"
          value={searchQuery}
          onChange={e => onSearchChange(e.target.value)}
          placeholder="Search projects..."
        />
      </div>
      <select className="filter-select" value={filterPhase} onChange={e => onPhaseChange(e.target.value)}>
        <option value="">Phase</option>
        {phases.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      <select className="filter-select" value={filterLead} onChange={e => onLeadChange(e.target.value)}>
        <option value="">Lead</option>
        {leads.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      <select className="filter-select" value={filterCity} onChange={e => onCityChange(e.target.value)}>
        <option value="">City</option>
        {cities.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
      {onHoldCount > 0 && (
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '12px', color: 'var(--fg-secondary)', fontFamily: 'var(--font-sans)', cursor: 'pointer', userSelect: 'none' }}>
          <input
            type="checkbox"
            checked={showOnHold}
            onChange={e => onShowOnHoldChange(e.target.checked)}
            style={{ accentColor: 'var(--accent)' }}
          />
          On Hold ({onHoldCount})
        </label>
      )}
      {issueCount > 0 && (
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '12px', color: 'var(--color-warning, #b45309)', fontFamily: 'var(--font-sans)', cursor: 'pointer', userSelect: 'none' }}>
          <input
            type="checkbox"
            checked={showIssuesOnly}
            onChange={e => onShowIssuesOnlyChange(e.target.checked)}
            style={{ accentColor: 'var(--color-warning, #b45309)' }}
          />
          Issues ({issueCount})
        </label>
      )}
    </div>
  )
}
