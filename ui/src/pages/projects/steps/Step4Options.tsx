import { Stack, Inline, Checkbox, Button } from '@ui/atoms'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useIntake } from '../IntakeContext'
import type { StepProps } from './StepProps'

export function Step4Options({ onNext, onBack }: StepProps) {
  const {
    communityEngagement, setCommunityEngagement,
    indigenousEngagement, setIndigenousEngagement,
    requiresRezoning, setRequiresRezoning,
    civicContribution, setCivicContribution,
  } = useIntake()

  return (
    <Stack gap="lg">
      <h2 className="text-sm font-medium text-ws-fg">Policy Options</h2>

      <Stack gap="md">
        <Checkbox
          checked={communityEngagement}
          onChange={setCommunityEngagement}
          label="Community Engagement"
          description="Project includes a community engagement component"
        />
        <Checkbox
          checked={indigenousEngagement}
          onChange={setIndigenousEngagement}
          label="Indigenous Engagement"
          description="Project includes Indigenous engagement or consultation"
        />
        <Checkbox
          checked={requiresRezoning}
          onChange={setRequiresRezoning}
          label="Requires Rezoning"
          description="Development requires a rezoning application"
        />
        <Checkbox
          checked={civicContribution}
          onChange={setCivicContribution}
          label="Civic Program Contribution"
          description="Project includes a civic art program contribution (10% of budget)"
        />
      </Stack>

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
        >
          Next: Review
        </Button>
      </Inline>
    </Stack>
  )
}
