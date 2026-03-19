import { Stack, Inline, Button } from '@ui/atoms'
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
      <div className="flex flex-col gap-1">
        <label htmlFor="neighbourhood" className="text-sm font-medium text-ws-fg">
          Neighbourhood
        </label>
        <input
          id="neighbourhood"
          type="text"
          list="neighbourhood-suggestions"
          value={neighbourhood}
          onChange={(e) => setNeighbourhood(e.target.value)}
          placeholder={neighbourhoods.length > 0 ? 'Select or type a neighbourhood' : 'Type a neighbourhood'}
          className="w-full rounded-lg border transition-colors bg-ws-panel-bg font-sans px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ws-accent focus:border-ws-accent border-ws-panel-border"
        />
        {neighbourhoods.length > 0 && (
          <datalist id="neighbourhood-suggestions">
            {neighbourhoods.map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
        )}
      </div>

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
