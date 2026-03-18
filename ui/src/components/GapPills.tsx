interface GapPillsProps {
  gaps: string[]
}

export function GapPills({ gaps }: GapPillsProps) {
  if (!gaps.length) {
    return <span style={{ color: 'var(--color-success)', fontSize: '11px' }}>Complete</span>
  }
  return (
    <div className="gap-pills">
      {gaps.map(g => (
        <span key={g} className="gap-pill">{g}</span>
      ))}
    </div>
  )
}
