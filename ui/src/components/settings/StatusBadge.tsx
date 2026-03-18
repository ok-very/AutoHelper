interface StatusBadgeProps {
  ok: boolean
  label: string
}

export function StatusBadge({ ok, label }: StatusBadgeProps) {
  return (
    <span className={`conn-badge ${ok ? 'ok' : 'off'}`}>
      <span className="conn-badge-dot" />
      {label}
    </span>
  )
}
