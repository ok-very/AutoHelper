import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { Stack, Inline, Card, Badge, Button, Spinner } from '@ui/atoms'
import { ChevronLeft, ChevronRight, Rocket, BookOpen } from 'lucide-react'
import { useIntake } from '../IntakeContext'
import { formatCurrency, BudgetCard } from '../utils'
import type { StepProps } from './StepProps'
import type { PolicyNote, StageInfo } from '@/lib/types'

export function Step5Review({ onBack }: StepProps) {
  const {
    selectedCity, municipality, projectType, projectName,
    developerName, neighbourhood,
    communityEngagement, indigenousEngagement, civicContribution, requiresRezoning,
    preview, previewLoading,
    submitting, submitError, handleSubmit,
    buildIntake,
  } = useIntake()

  const intake = buildIntake()

  return (
    <Stack gap="lg">
      {/* Project Summary */}
      <Card padding="md">
        <h3 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide mb-3">Project Summary</h3>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <dt className="text-ws-text-secondary">Municipality</dt>
          <dd className="text-ws-fg">{selectedCity?.city_name ?? municipality}</dd>
          <dt className="text-ws-text-secondary">Type</dt>
          <dd className="text-ws-fg capitalize">{projectType?.replace(/_/g, ' ')}</dd>
          <dt className="text-ws-text-secondary">Name</dt>
          <dd className="text-ws-fg font-medium">{projectName}</dd>
          {developerName && (
            <>
              <dt className="text-ws-text-secondary">Developer</dt>
              <dd className="text-ws-fg">{developerName}</dd>
            </>
          )}
          {neighbourhood && (
            <>
              <dt className="text-ws-text-secondary">Neighbourhood</dt>
              <dd className="text-ws-fg">{neighbourhood}</dd>
            </>
          )}
          <dt className="text-ws-text-secondary">Construction cost</dt>
          <dd className="text-ws-fg tabular-nums">{formatCurrency(intake.construction_cost)}</dd>
          {intake.unit_count != null && (
            <>
              <dt className="text-ws-text-secondary">Units</dt>
              <dd className="text-ws-fg tabular-nums">{intake.unit_count}</dd>
            </>
          )}
          {intake.floor_area_sqm != null && (
            <>
              <dt className="text-ws-text-secondary">Floor area</dt>
              <dd className="text-ws-fg tabular-nums">{intake.floor_area_sqm.toLocaleString()} sqm</dd>
            </>
          )}
        </dl>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {communityEngagement && <Badge variant="info" size="xs">Community Engagement</Badge>}
          {indigenousEngagement && <Badge variant="info" size="xs">Indigenous Engagement</Badge>}
          {civicContribution && <Badge variant="info" size="xs">Civic Contribution</Badge>}
          {requiresRezoning && <Badge variant="warning" size="xs">Rezoning</Badge>}
        </div>
      </Card>

      {/* Budget */}
      <BudgetCard budget={preview?.budget ?? null} loading={previewLoading} />

      {/* Tasks per stage */}
      {preview && preview.stages.length > 0 && (
        <Card padding="md">
          <h3 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide mb-3">
            Tasks by Stage ({preview.total_tasks} total)
          </h3>
          <div className="flex flex-col gap-2">
            {preview.stages.map((stage: StageInfo) => (
              <div key={stage.number} className="flex items-center justify-between text-sm">
                <span className="text-ws-fg">{stage.name}</span>
                <span className="text-ws-text-secondary tabular-nums">{stage.task_count}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Policy Guidance */}
      {preview && <PolicyGuidanceCard tasks={preview.tasks} stages={preview.stages} />}

      {/* Error */}
      {submitError && (
        <p className="text-sm text-ws-error">{submitError}</p>
      )}

      {/* Actions */}
      <Inline justify="between">
        <Button
          variant="ghost"
          size="sm"
          leftSection={<ChevronLeft className="w-4 h-4" />}
          onClick={onBack}
        >
          Back
        </Button>
        <Inline gap="sm">
          <Button
            variant="secondary"
            size="md"
            onClick={() => handleSubmit(false)}
            disabled={submitting}
          >
            {submitting ? <Spinner size="sm" /> : 'Save Draft'}
          </Button>
          <Button
            variant="primary"
            size="md"
            leftSection={<Rocket className="w-4 h-4" />}
            onClick={() => handleSubmit(true)}
            disabled={submitting}
          >
            {submitting ? <Spinner size="sm" /> : 'Create & Provision'}
          </Button>
        </Inline>
      </Inline>
    </Stack>
  )
}

// ---------------------------------------------------------------------------
// Policy Guidance (matches ProjectDetailPage pattern)
// ---------------------------------------------------------------------------

function PolicyGuidanceCard({
  tasks,
  stages,
}: {
  tasks: { temp_id: string; name: string; stage: number; policy_notes: PolicyNote[] }[]
  stages: StageInfo[]
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const notesByStage = useMemo(() => {
    const map = new Map<number, { taskName: string; notes: PolicyNote[] }[]>()
    for (const task of tasks) {
      if (!task.policy_notes || task.policy_notes.length === 0) continue
      if (!map.has(task.stage)) map.set(task.stage, [])
      map.get(task.stage)!.push({ taskName: task.name, notes: task.policy_notes })
    }
    return map
  }, [tasks])

  if (notesByStage.size === 0) return null

  const stageNameMap = Object.fromEntries(stages.map(s => [s.number, s.name]))

  const toggleStage = (stage: number) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(stage)) next.delete(stage)
      else next.add(stage)
      return next
    })
  }

  const totalNotes = Array.from(notesByStage.values()).reduce(
    (sum, taskNotes) => sum + taskNotes.reduce((s, t) => s + t.notes.length, 0), 0
  )

  return (
    <Card padding="md">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen className="w-4 h-4 text-ws-text-secondary" />
        <h3 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide">
          Policy Guidance ({totalNotes} notes)
        </h3>
      </div>
      <div className="flex flex-col gap-1">
        {Array.from(notesByStage.entries())
          .sort(([a], [b]) => a - b)
          .map(([stage, taskNotes]) => {
            const isOpen = expanded.has(stage)
            return (
              <div key={stage}>
                <button
                  className="flex items-center gap-1.5 text-sm text-ws-fg w-full text-left py-1"
                  onClick={() => toggleStage(stage)}
                >
                  <ChevronRight className={clsx('w-3.5 h-3.5 transition-transform', isOpen && 'rotate-90')} />
                  <span className="font-medium">{stageNameMap[stage] ?? `Stage ${stage}`}</span>
                  <span className="text-ws-text-secondary text-xs ml-1">
                    ({taskNotes.reduce((sum, t) => sum + t.notes.length, 0)})
                  </span>
                </button>
                {isOpen && (
                  <div className="ml-5 flex flex-col gap-2 pb-2">
                    {taskNotes.map(({ taskName, notes }, ti) => (
                      <div key={ti}>
                        <p className="text-xs font-medium text-ws-text-secondary mb-1">{taskName}</p>
                        {notes.map((note, ni) => (
                          <div key={ni} className="text-xs text-ws-fg pl-2 border-l-2 border-ws-panel-border mb-1">
                            <span className="font-medium">{note.topic}:</span>{' '}
                            <span className="text-ws-text-secondary">{note.text}</span>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
      </div>
    </Card>
  )
}
