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
  memberMap: Record<string, string>
}

/** Resolve compound initials like "JB/NY" to "JB/NY — Jane, Neal" */
function resolveLeadLabel(code: string, memberMap: Record<string, string>): string {
  if (!code || Object.keys(memberMap).length === 0) return code
  const parts = code.split('/')
  const names = parts
    .map(p => memberMap[p.trim()])
    .filter(Boolean)
  if (names.length === 0) return code
  const shortNames = names.map(n => n.split(' ')[0]) // first name only
  return `${code} — ${shortNames.join(', ')}`
}

/** Filter out junk city values that contain budget text, pipes, underscores, trailing commas, etc. */
function cleanCities(cities: string[]): string[] {
  return cities.filter(c => {
    if (!c || c === 'TBC' || c === 'TBD') return false
    if (/[$|_]{2,}|TOTAL|PENDING|Budget/i.test(c)) return false
    if (/\d{4}/.test(c)) return false // years leaked in
    if (/[,(]$/.test(c.trim())) return false // trailing comma or paren
    if (/\(\$/.test(c)) return false // "($ ..." budget fragment
    return true
  })
}

const s = {
  bar: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    alignItems: 'center',
    gap: '8px',
    fontFamily: 'var(--font-sans)',
    fontSize: '12px',
  },
  searchWrap: {
    position: 'relative' as const,
    flex: '1 1 200px',
    maxWidth: '320px',
  },
  searchIcon: {
    position: 'absolute' as const,
    left: '8px',
    top: '50%',
    transform: 'translateY(-50%)',
    color: 'var(--fg-disabled)',
    pointerEvents: 'none' as const,
  },
  toggle: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    cursor: 'pointer',
    userSelect: 'none' as const,
    fontFamily: 'var(--font-sans)',
    fontSize: '12px',
  },
  separator: {
    width: '1px',
    height: '16px',
    background: 'var(--border)',
    flexShrink: 0,
  },
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
  memberMap,
}: FilterBarProps) {
  const cleanedCities = cleanCities(cities)

  return (
    <div style={s.bar}>
      <div style={s.searchWrap}>
        <Search size={13} style={s.searchIcon} />
        <input
          type="text"
          className="search-input"
          value={searchQuery}
          onChange={e => onSearchChange(e.target.value)}
          placeholder="Search projects..."
          style={{ width: '100%' }}
        />
      </div>

      <select className="filter-select" value={filterPhase} onChange={e => onPhaseChange(e.target.value)}>
        <option value="">All phases</option>
        {phases.map(o => <option key={o} value={o}>{o}</option>)}
      </select>

      <select className="filter-select" value={filterLead} onChange={e => onLeadChange(e.target.value)}>
        <option value="">All leads</option>
        {leads.map(o => (
          <option key={o} value={o}>{resolveLeadLabel(o, memberMap)}</option>
        ))}
      </select>

      <select className="filter-select" value={filterCity} onChange={e => onCityChange(e.target.value)}>
        <option value="">All cities</option>
        {cleanedCities.map(o => <option key={o} value={o}>{o}</option>)}
      </select>

      <span style={s.separator} />

      {onHoldCount > 0 && (
        <label style={{ ...s.toggle, color: showOnHold ? 'var(--fg)' : 'var(--fg-secondary)' }}>
          <input
            type="checkbox"
            checked={showOnHold}
            onChange={e => onShowOnHoldChange(e.target.checked)}
            style={{ accentColor: 'var(--accent)' }}
          />
          On hold ({onHoldCount})
        </label>
      )}

      {issueCount > 0 && (
        <label style={{ ...s.toggle, color: showIssuesOnly ? 'var(--color-warning, #B89B5E)' : 'var(--fg-secondary)' }}>
          <input
            type="checkbox"
            checked={showIssuesOnly}
            onChange={e => onShowIssuesOnlyChange(e.target.checked)}
            style={{ accentColor: 'var(--color-warning, #B89B5E)' }}
          />
          {issueCount} issues
        </label>
      )}
    </div>
  )
}
