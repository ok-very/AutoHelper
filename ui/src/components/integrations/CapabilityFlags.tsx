import { Badge } from '@/ui/atoms/Badge'
import type { ProviderCapability } from './registry'

interface CapabilityFlagsProps {
  capabilities: ProviderCapability[]
  activeKeys?: string[]
}

export function CapabilityFlags({ capabilities, activeKeys }: CapabilityFlagsProps) {
  return (
    <span className="integration-card-capabilities">
      {capabilities.map(cap => (
        <Badge
          key={cap.key}
          variant={activeKeys?.includes(cap.key) ? 'info' : 'neutral'}
          size="xs"
        >
          {cap.label}
        </Badge>
      ))}
    </span>
  )
}
