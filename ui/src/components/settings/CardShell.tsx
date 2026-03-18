import type { ReactNode } from 'react'

interface CardShellProps {
  icon: ReactNode
  iconBg?: string
  title: string
  subtitle?: string
  badge?: ReactNode
  children: ReactNode
}

export function CardShell({ icon, iconBg, title, subtitle, badge, children }: CardShellProps) {
  return (
    <div className="card-shell">
      <div className="card-shell-header">
        <div className={`card-shell-icon ${iconBg ?? ''}`}>{icon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="card-shell-title">{title}</span>
            {badge}
          </div>
          {subtitle && <div className="card-shell-subtitle">{subtitle}</div>}
        </div>
      </div>
      <div className="card-shell-body">{children}</div>
    </div>
  )
}
