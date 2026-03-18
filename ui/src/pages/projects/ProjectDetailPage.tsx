import { useState, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import { ExternalLink, Rocket, ArrowLeft, Clock, CalendarDays, ChevronRight, BookOpen } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { Card, Badge, Button, Spinner } from '@ui/atoms'
import { api } from '@/lib/api'
import type { ProjectRecord, ProjectStatus, BudgetCalculation, StageInfo, ResolvedManifest, PolicyNote } from '@/lib/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_BADGE: Record<ProjectStatus, { variant: 'neutral' | 'info' | 'success' | 'default' | 'warning'; label: string }> = {
  draft: { variant: 'neutral', label: 'Draft' },
  provisioning: { variant: 'warning', label: 'Provisioning...' },
  provisioned: { variant: 'info', label: 'Provisioned' },
  active: { variant: 'success', label: 'Active' },
  completed: { variant: 'default', label: 'Completed' },
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(value)
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' })
}

function getProjectId(): string | null {
  const parts = window.location.pathname.split('/')
  const last = parts[parts.length - 1]
  return last && last !== 'projects' ? last : null
}

// ---------------------------------------------------------------------------
// Budget Card
// ---------------------------------------------------------------------------

function BudgetCard({ budget }: { budget: BudgetCalculation }) {
  return (
    <Card padding="md">
      <h3 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide mb-3">Budget</h3>
      <div className="flex flex-col gap-1.5 text-sm">
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Contribution rate</span>
          <span className="text-ws-fg tabular-nums">{formatPercent(budget.contribution_rate)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Cost basis</span>
          <span className="text-ws-fg">{budget.cost_basis}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Eligible cost</span>
          <span className="text-ws-fg tabular-nums">{formatCurrency(budget.eligible_cost)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Art contribution</span>
          <span className="text-ws-fg tabular-nums">{formatCurrency(budget.art_contribution)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Maintenance reserve ({formatPercent(budget.maintenance_reserve_rate)})</span>
          <span className="text-ws-fg tabular-nums">{formatCurrency(budget.maintenance_reserve)}</span>
        </div>
        <div className="flex justify-between border-t border-ws-panel-border pt-1.5 mt-1">
          <span className="font-medium text-ws-fg">Total</span>
          <span className="font-semibold text-ws-fg tabular-nums">{formatCurrency(budget.total)}</span>
        </div>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Stage Breakdown Card
// ---------------------------------------------------------------------------

function StageBreakdownCard({ stages, totalTasks }: { stages: StageInfo[]; totalTasks: number }) {
  const maxCount = Math.max(...stages.map((s) => s.task_count), 1)
  return (
    <Card padding="md">
      <h3 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide mb-3">
        Tasks by Stage ({totalTasks} total)
      </h3>
      <div className="flex flex-col gap-2">
        {stages.map((stage) => (
          <div key={stage.number} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-ws-fg">{stage.name}</span>
              <span className="text-ws-text-secondary tabular-nums">{stage.task_count}</span>
            </div>
            <div className="h-1.5 w-full bg-ws-bg rounded-full overflow-hidden">
              <div
                className="h-full bg-ws-accent rounded-full transition-all"
                style={{ width: `${(stage.task_count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Policy Guidance Card
// ---------------------------------------------------------------------------

function PolicyGuidanceCard({
  tasks,
  stages,
}: {
  tasks: { temp_id: string; name: string; stage: number; policy_notes: PolicyNote[] }[]
  stages: StageInfo[]
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  // Collect notes grouped by stage
  const notesByStage = new Map<number, { taskName: string; notes: PolicyNote[] }[]>()
  for (const task of tasks) {
    if (!task.policy_notes || task.policy_notes.length === 0) continue
    if (!notesByStage.has(task.stage)) notesByStage.set(task.stage, [])
    notesByStage.get(task.stage)!.push({ taskName: task.name, notes: task.policy_notes })
  }

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

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function ProjectDetailPage() {
  const [project, setProject] = useState<ProjectRecord | null>(null)
  const [preview, setPreview] = useState<ResolvedManifest | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [provisioning, setProvisioning] = useState(false)
  const [provisionError, setProvisionError] = useState<string | null>(null)

  const projectId = getProjectId()

  // ---------------------------------------------------------------------------
  // Load project
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!projectId) {
      setError('No project ID in URL')
      setLoading(false)
      return
    }
    setLoading(true)
    api.projects.get(projectId)
      .then((data: ProjectRecord) => {
        setProject(data)
        // Fetch preview for stage breakdown
        return api.projects.preview(data.intake).then((p: ResolvedManifest) => setPreview(p)).catch(() => {})
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [projectId])

  // ---------------------------------------------------------------------------
  // Provision handler
  // ---------------------------------------------------------------------------
  const handleProvision = useCallback(async () => {
    if (!projectId || !project) return
    setProvisioning(true)
    setProvisionError(null)
    try {
      const updated = await api.projects.provision(projectId)
      setProject(updated)
    } catch (err: any) {
      setProvisionError(err.message ?? 'Provisioning failed')
    } finally {
      setProvisioning(false)
    }
  }, [projectId, project])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <ModuleLayout module="projects" activePage="detail">
        <div className="flex items-center justify-center py-16">
          <Spinner size="lg" />
        </div>
      </ModuleLayout>
    )
  }

  if (error || !project) {
    return (
      <ModuleLayout module="projects" activePage="detail">
        <div className="flex flex-col gap-4">
          <Card padding="lg">
            <p className="text-sm text-ws-error">{error ?? 'Project not found'}</p>
          </Card>
          <Button
            variant="ghost"
            size="sm"
            leftSection={<ArrowLeft className="w-4 h-4" />}
            onClick={() => { window.location.href = '/projects' }}
          >
            Back to Projects
          </Button>
        </div>
      </ModuleLayout>
    )
  }

  const status = STATUS_BADGE[project.status] ?? STATUS_BADGE.draft
  const clickupUrl = project.clickup_list_id && project.clickup_workspace_id
    ? `https://app.clickup.com/${project.clickup_workspace_id}/v/li/${project.clickup_list_id}`
    : null

  return (
    <ModuleLayout module="projects" activePage="detail">
      <div className="flex flex-col gap-6 max-w-3xl">
        {/* Back link */}
        <Button
          variant="ghost"
          size="xs"
          leftSection={<ArrowLeft className="w-3.5 h-3.5" />}
          onClick={() => { window.location.href = '/projects' }}
          className="self-start"
        >
          All Projects
        </Button>

        {/* Header */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-lg font-semibold text-ws-fg">{project.project_name}</h1>
            <Badge variant={status.variant} size="sm">{status.label}</Badge>
            <Badge variant="light" size="xs">{project.city_name}</Badge>
          </div>
          {project.developer_name && (
            <p className="text-sm text-ws-text-secondary">{project.developer_name}</p>
          )}
          <p className="text-xs text-ws-text-secondary capitalize">
            {project.project_type.replace(/_/g, ' ')}
          </p>
        </div>

        {/* Provisioning warning */}
        {project.status === 'provisioning' && (
          <Card padding="md" className="border-ws-warning/30 bg-ws-warning/5">
            <p className="text-sm text-ws-fg">
              A previous provisioning attempt was interrupted. Check ClickUp for partial data before retrying.
              {project.clickup_list_id && (
                <> ClickUp list was created (ID: {project.clickup_list_id}).</>
              )}
            </p>
          </Card>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 flex-wrap">
          {project.status === 'draft' && (
            <Button
              variant="primary"
              size="sm"
              leftSection={provisioning ? <Spinner size="sm" /> : <Rocket className="w-4 h-4" />}
              onClick={handleProvision}
              disabled={provisioning}
            >
              {provisioning ? 'Provisioning...' : 'Provision to ClickUp'}
            </Button>
          )}
          {clickupUrl && (
            <Button
              variant="secondary"
              size="sm"
              rightSection={<ExternalLink className="w-3.5 h-3.5" />}
              onClick={() => window.open(clickupUrl, '_blank')}
            >
              Open in ClickUp
            </Button>
          )}
        </div>
        {provisionError && <p className="text-sm text-ws-error">{provisionError}</p>}

        {/* Budget */}
        {project.budget && <BudgetCard budget={project.budget} />}

        {/* Stage breakdown */}
        {preview && preview.stages.length > 0 && (
          <StageBreakdownCard stages={preview.stages} totalTasks={preview.total_tasks} />
        )}

        {/* Policy guidance */}
        {preview && (
          <PolicyGuidanceCard tasks={preview.tasks} stages={preview.stages} />
        )}

        {/* Timestamps */}
        <Card padding="md">
          <div className="flex flex-col gap-2 text-sm">
            <div className="flex items-center gap-2 text-ws-text-secondary">
              <CalendarDays className="w-4 h-4" />
              <span>Created {formatDate(project.created_at)}</span>
            </div>
            <div className="flex items-center gap-2 text-ws-text-secondary">
              <Clock className="w-4 h-4" />
              <span>Updated {formatDate(project.updated_at)}</span>
            </div>
            {project.provisioned_at && (
              <div className="flex items-center gap-2 text-ws-text-secondary">
                <Rocket className="w-4 h-4" />
                <span>Provisioned {formatDate(project.provisioned_at)}</span>
              </div>
            )}
          </div>
        </Card>
      </div>
    </ModuleLayout>
  )
}
