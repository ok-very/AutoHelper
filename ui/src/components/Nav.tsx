interface NavProps {
  active: 'settings' | 'health' | 'recon' | 'directory' | 'submissions' | 'sub-settings'
}

const links = [
  { href: '/artists-settings', key: 'settings', label: 'Settings' },
  { href: '/artists-health', key: 'health', label: 'Health' },
  { href: '/artists-recon', key: 'recon', label: 'Reconciliation' },
  { href: '/artists-dashboard', key: 'directory', label: 'Directory' },
  { href: '/submissions-settings', key: 'sub-settings', label: 'Sub Settings' },
  { href: '/submissions', key: 'submissions', label: 'Submissions' },
] as const

export function Nav({ active }: NavProps) {
  return (
    <nav className="artist-nav">
      {links.map(l => (
        <a
          key={l.key}
          href={l.href}
          className={`nav-link${l.key === active ? ' active' : ''}`}
        >
          {l.label}
        </a>
      ))}
    </nav>
  )
}
