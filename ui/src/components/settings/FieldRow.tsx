import type { ReactNode } from 'react'

interface FieldRowProps {
  label: string
  children: ReactNode
}

export function FieldRow({ label, children }: FieldRowProps) {
  return (
    <div className="field-row">
      <span className="field-row-label">{label}</span>
      <div className="field-row-value">{children}</div>
    </div>
  )
}
