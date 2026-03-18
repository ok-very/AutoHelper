import { Stack, Inline, Select, Button } from '@ui/atoms'
import { TextInput } from '@ui/atoms/TextInput'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useIntake } from '../IntakeContext'
import type { StepProps } from './StepProps'

export function Step2Details({ onNext, onBack }: StepProps) {
  const {
    projectName, setProjectName,
    developerName, setDeveloperName,
    neighbourhood, setNeighbourhood,
    cityOverlay, canAdvance,
  } = useIntake()

  const neighbourhoods = cityOverlay?.neighbourhoods ?? []

  return (
    <Stack gap="lg">
      <TextInput
        label="Project Name"
        required
        value={projectName}
        onChange={(e) => setProjectName(e.target.value)}
        placeholder="e.g. Polygon Lennox"
      />
      <TextInput
        label="Developer Name"
        value={developerName}
        onChange={(e) => setDeveloperName(e.target.value)}
        placeholder="e.g. Polygon Homes"
      />
      {neighbourhoods.length > 0 && (
        <Select
          label="Neighbourhood"
          value={neighbourhood || null}
          onChange={(v) => setNeighbourhood(v ?? '')}
          data={neighbourhoods.map((n) => ({ value: n, label: n }))}
          placeholder="None"
        />
      )}

      <Inline justify="between">
        <Button
          variant="ghost"
          size="sm"
          leftSection={<ChevronLeft className="w-4 h-4" />}
          onClick={onBack}
        >
          Back
        </Button>
        <Button
          variant="primary"
          size="sm"
          rightSection={<ChevronRight className="w-4 h-4" />}
          onClick={onNext}
          disabled={!canAdvance}
        >
          Next: Financials
        </Button>
      </Inline>
    </Stack>
  )
}
