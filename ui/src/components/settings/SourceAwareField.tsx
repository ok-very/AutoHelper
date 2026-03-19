import { FieldRow } from './FieldRow'
import { ConnectedValue } from './ConnectedValue'
import { SourceBadge } from '@/components/integrations/SourceBadge'
import type { IntegrationFieldStatus } from '@/lib/api'

export function SourceAwareField({
  field, label, placeholder, configKey, onSave,
}: {
  field: IntegrationFieldStatus
  label: string
  placeholder?: string
  configKey: string
  onSave: (key: string, value: string) => Promise<void>
}) {
  if (field.source === 'env') {
    return (
      <FieldRow label={label}>
        <div className="field-row-inline">
          <span className="configured-value">{field.value}</span>
          <SourceBadge source="env" />
        </div>
      </FieldRow>
    )
  }
  return (
    <FieldRow label={label}>
      <ConnectedValue
        value={field.value}
        placeholder={placeholder}
        onSave={v => onSave(configKey, v)}
      />
    </FieldRow>
  )
}
