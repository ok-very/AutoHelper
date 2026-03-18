import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import { FolderOpen, Plus, ChevronRight } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { Card, Badge, Button, Spinner } from '@ui/atoms'
import { api } from '@/lib/api'
import type { ProjectRecord, ProjectStatus } from '@/lib/types'

const STATUS_BADGE: Record<ProjectStatus, { variant: 'neutral' | 'info' | 'success' | 'default'; label: string }> = {
  draft: { variant: 'neutral', label: 'Draft' },
  provisioned: { variant: 'info', label: 'Provisioned' },
  active: { variant: 'success', label: 'Active' },
  completed: { variant: 'default', label: 'Completed' },
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(value)
}

export function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.projects.list()
      .then(setProjects)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <ModuleLayout module="projects" activePage="list">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FolderOpen className="w-5 h-5 text-ws-text-secondary" />
            <h1 className="text-lg font-semibold text-ws-fg">Projects</h1>
          </div>
          <Button
            variant="primary"
            size="sm"
            leftSection={<Plus className="w-3.5 h-3.5" />}
            onClick={() => { window.location.href = '/projects/new' }}
          >
            New Project
          </Button>
        </div>

        {/* Content */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Spinner size="lg" />
          </div>
        )}

        {error && (
          <Card padding="lg">
            <p className="text-sm text-ws-error">{error}</p>
          </Card>
        )}

        {!loading && !error && projects.length === 0 && (
          <Card padding="lg">
            <div className="flex flex-col items-center gap-3 py-8">
              <FolderOpen className="w-10 h-10 text-ws-text-secondary opacity-40" />
              <p className="text-sm text-ws-text-secondary">No projects yet</p>
              <Button
                variant="secondary"
                size="sm"
                leftSection={<Plus className="w-3.5 h-3.5" />}
                onClick={() => { window.location.href = '/projects/new' }}
              >
                Create your first project
              </Button>
            </div>
          </Card>
        )}

        {!loading && !error && projects.length > 0 && (
          <Card padding="none">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ws-panel-border text-left text-ws-text-secondary">
                  <th className="px-4 py-2.5 font-medium">Name</th>
                  <th className="px-4 py-2.5 font-medium">Developer</th>
                  <th className="px-4 py-2.5 font-medium">Municipality</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium text-right">Art Budget</th>
                  <th className="px-4 py-2.5 font-medium text-right">Tasks</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => {
                  const status = STATUS_BADGE[project.status] ?? STATUS_BADGE.draft
                  return (
                    <tr
                      key={project.id}
                      className="border-b border-ws-panel-border last:border-b-0 hover:bg-ws-row-expanded-bg cursor-pointer transition-colors"
                      onClick={() => { window.location.href = `/projects/${project.id}` }}
                    >
                      <td className="px-4 py-3 font-medium text-ws-fg">{project.project_name}</td>
                      <td className="px-4 py-3 text-ws-text-secondary">{project.developer_name ?? '-'}</td>
                      <td className="px-4 py-3">
                        <Badge variant="light" size="xs">{project.city_name}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={status.variant} size="xs">{status.label}</Badge>
                      </td>
                      <td className="px-4 py-3 text-right text-ws-fg tabular-nums">
                        {project.budget ? formatCurrency(project.budget.total) : '-'}
                      </td>
                      <td className="px-4 py-3 text-right text-ws-text-secondary tabular-nums">
                        {project.resolved_task_count}
                      </td>
                      <td className="px-4 py-3">
                        <ChevronRight className="w-4 h-4 text-ws-text-secondary" />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </Card>
        )}
      </div>
    </ModuleLayout>
  )
}
