import { Stack, Inline, Button } from '@ui/atoms'
import { TextInput } from '@ui/atoms/TextInput'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useIntake } from '../IntakeContext'
import { BudgetCard } from '../utils'
import type { StepProps } from './StepProps'

export function Step3Financials({ onNext, onBack }: StepProps) {
  const {
    constructionCost, setConstructionCost,
    unitCount, setUnitCount,
    floorArea, setFloorArea,
    fsr, setFsr,
    preview, previewLoading, canAdvance,
  } = useIntake()

  return (
    <Stack gap="lg">
      <TextInput
        label="Construction Cost"
        required
        type="number"
        min={0}
        value={constructionCost}
        onChange={(e) => setConstructionCost(e.target.value)}
        placeholder="e.g. 50000000"
      />

      <h3 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide">
        Development Application Data
      </h3>

      <div className="grid grid-cols-3 gap-4">
        <TextInput
          label="FSR"
          type="number"
          min={0}
          step={0.01}
          value={fsr}
          onChange={(e) => setFsr(e.target.value)}
          placeholder="e.g. 5.2"
        />
        <TextInput
          label="Units"
          type="number"
          min={0}
          value={unitCount}
          onChange={(e) => setUnitCount(e.target.value)}
          placeholder="e.g. 200"
        />
        <TextInput
          label="Floor Area (sqm)"
          type="number"
          min={0}
          value={floorArea}
          onChange={(e) => setFloorArea(e.target.value)}
          placeholder="e.g. 15000"
        />
      </div>

      <BudgetCard budget={preview?.budget ?? null} loading={previewLoading} />

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
          Next: Policy Options
        </Button>
      </Inline>
    </Stack>
  )
}
