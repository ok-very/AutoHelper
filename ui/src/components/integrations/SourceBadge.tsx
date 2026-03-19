import type { SourceType } from './registry'

const LABELS: Partial<Record<SourceType, string>> = {
  env: 'ENV',
  oauth: 'OAuth',
  config: 'Config',
  pairing: 'Paired',
}

export function SourceBadge({ source }: { source?: SourceType }) {
  if (!source || source === 'none') return null
  const label = LABELS[source]
  if (!label) return null
  return <span className="source-badge">{label}</span>
}
