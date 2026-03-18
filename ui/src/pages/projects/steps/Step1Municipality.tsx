import { Stack, Inline, Select, Button, Spinner } from '@ui/atoms'
import { RadioGroup } from '@ui/atoms/RadioGroup'
import { ChevronRight } from 'lucide-react'
import { useIntake } from '../IntakeContext'
import { formatPercent } from '../utils'
import type { StepProps } from './StepProps'

const PROJECT_TYPE_OPTIONS = [
  { value: 'private_development', label: 'Private Development', description: 'Residential or commercial rezoning' },
  { value: 'civic', label: 'Civic', description: 'Municipal or government project' },
  { value: 'community', label: 'Community', description: 'Community-driven public art project' },
]

export function Step1Municipality({ onNext }: StepProps) {
  const {
    municipality, setMunicipality,
    projectType, setProjectType,
    cities, citiesLoading, selectedCity,
    canAdvance,
  } = useIntake()

  return (
    <Stack gap="lg">
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-ws-fg">
          Municipality <span className="text-ws-error">*</span>
        </label>
        {citiesLoading ? (
          <div className="flex items-center gap-2 text-sm text-ws-text-secondary">
            <Spinner size="sm" />
            <span>Loading cities...</span>
          </div>
        ) : (
          <Select
            value={municipality || null}
            onChange={(v) => setMunicipality(v ?? '')}
            data={cities.map((c) => ({
              value: c.city_id,
              label: `${c.city_name} (v${c.policy_version})`,
            }))}
            placeholder="Select a municipality..."
          />
        )}
        {selectedCity && (
          <p className="text-xs text-ws-text-secondary">
            Contribution rate: {formatPercent(selectedCity.contribution_rate)}
            {selectedCity.task_override_count > 0 && (
              <> &middot; {selectedCity.task_override_count} task override{selectedCity.task_override_count !== 1 ? 's' : ''}</>
            )}
          </p>
        )}
      </div>

      <RadioGroup
        name="project_type"
        label="Project Type"
        value={projectType}
        onChange={(v) => setProjectType(v as any)}
        options={PROJECT_TYPE_OPTIONS}
        nullable={false}
      />

      <Inline justify="end">
        <Button
          variant="primary"
          size="sm"
          rightSection={<ChevronRight className="w-4 h-4" />}
          onClick={onNext}
          disabled={!canAdvance}
        >
          Next: Project Details
        </Button>
      </Inline>
    </Stack>
  )
}
