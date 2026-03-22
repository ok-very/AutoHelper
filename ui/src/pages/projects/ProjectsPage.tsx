import { useState, useEffect, useCallback } from 'react'
import { clsx } from 'clsx'
import { FolderOpen, Plus, ChevronRight, Download, Loader2, CheckCircle2, XCircle } from 'lucide-react'
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

  // Monday import state
  const [showMondayImport, setShowMondayImport] = useState(false)
  const [mondayProjects, setMondayProjects] = useState<any[]>([])
  const [mondayLoading, setMondayLoading] = useState(false)
  const [mondayImporting, setMondayImporting] = useState(false)
  const [mondayProgress, setMondayProgress] = useState<{ done: number; total: number; current: string; errors: string[] }>({ done: 0, total: 0, current: '', errors: [] })

  useEffect(() => {
    api.projects.list()
      .then(setProjects)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const handleLoadMonday = useCallback(async () => {
    setShowMondayImport(true)
    setMondayLoading(true)
    try {
      const data = await api.monday.overview()
      // Filter to Active Projects group, skip empty/placeholder rows
      const active = data.filter((p: any) => p.group === 'Active Projects' && p.municipality)
      setMondayProjects(active)
    } catch (err: any) {
      setError(err.message || 'Failed to load Monday projects')
    } finally {
      setMondayLoading(false)
    }
  }, [])

  const handleImportAll = useCallback(async () => {
    if (mondayImporting) return
    setMondayImporting(true)
    const toImport = mondayProjects.filter((p: any) => p.project_board_id)
    setMondayProgress({ done: 0, total: toImport.length, current: '', errors: [] })

    for (let i = 0; i < toImport.length; i++) {
      const proj = toImport[i]
      setMondayProgress(prev => ({ ...prev, current: proj.name, done: i }))
      try {
        await api.monday.importBoard(proj.project_board_id, proj.municipality, proj.phase)
      } catch (err: any) {
        setMondayProgress(prev => ({
          ...prev,
          errors: [...prev.errors, `${proj.name}: ${err.message || 'failed'}`],
        }))
      }
    }

    setMondayProgress(prev => ({ ...prev, done: toImport.length, current: '' }))
    setMondayImporting(false)
    // Refresh project list
    api.projects.list().then(setProjects).catch(() => {})
  }, [mondayProjects, mondayImporting])

  return (
    <ModuleLayout module="projects" activePage="list">
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FolderOpen className="w-5 h-5 text-ws-text-secondary" />
            <h1 className="text-lg font-semibold text-ws-fg">Projects</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              leftSection={<Download className="w-3.5 h-3.5" />}
              onClick={handleLoadMonday}
            >
              Import from Monday
            </Button>
            <Button
              variant="primary"
              size="sm"
              leftSection={<Plus className="w-3.5 h-3.5" />}
              onClick={() => { window.location.href = '/projects/new' }}
            >
              New Project
            </Button>
          </div>
        </div>

        {/* Monday Import Panel */}
        {showMondayImport && (
          <Card padding="md">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-ws-fg">
                  Monday.com Import
                </span>
                <button
                  className="text-xs text-ws-text-secondary hover:text-ws-fg"
                  onClick={() => setShowMondayImport(false)}
                >
                  Close
                </button>
              </div>

              {mondayLoading && (
                <div className="flex items-center gap-2 text-sm text-ws-text-secondary">
                  <Loader2 className="w-4 h-4 animate-spin" /> Loading projects from Monday overview...
                </div>
              )}

              {!mondayLoading && mondayProjects.length > 0 && (
                <>
                  <p className="text-xs text-ws-text-secondary">
                    {mondayProjects.length} active projects found. Import creates ProjectRecord, provisions ClickUp with city policy matrix, posts correspondence to tasks.
                  </p>

                  {!mondayImporting && mondayProgress.done === 0 && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleImportAll}
                    >
                      Import all {mondayProjects.length} projects
                    </Button>
                  )}

                  {mondayImporting && (
                    <div className="flex items-center gap-2 text-sm text-ws-fg">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      {mondayProgress.done}/{mondayProgress.total}: {mondayProgress.current}
                    </div>
                  )}

                  {!mondayImporting && mondayProgress.done > 0 && (
                    <div className="flex items-center gap-2 text-sm text-ws-success">
                      <CheckCircle2 className="w-4 h-4" />
                      Imported {mondayProgress.done} projects
                      {mondayProgress.errors.length > 0 && (
                        <span className="text-ws-error">
                          ({mondayProgress.errors.length} errors)
                        </span>
                      )}
                    </div>
                  )}

                  {mondayProgress.errors.length > 0 && (
                    <div className="text-xs text-ws-error flex flex-col gap-1 max-h-32 overflow-auto">
                      {mondayProgress.errors.map((e, i) => (
                        <div key={i} className="flex items-start gap-1">
                          <XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          {e}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {!mondayLoading && mondayProjects.length === 0 && (
                <p className="text-xs text-ws-text-secondary">
                  No active projects found on the Monday overview board.
                </p>
              )}
            </div>
          </Card>
        )}

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
