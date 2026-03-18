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
      <TextInput
        label="Unit Count"
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
