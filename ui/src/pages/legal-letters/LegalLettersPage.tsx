import { useState, useEffect } from 'react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { Badge } from '@/ui/atoms/Badge'
import { Button } from '@/ui/atoms/Button'
import { Spinner } from '@/ui/atoms/Spinner'
import { Card } from '@/ui/atoms/Card'
import { api } from '@/lib/api'

interface FieldStatus {
  field: string
  value: string | null
  filled: boolean
}

interface TemplatePreview {
  template_key: string
  template_name: string
  project_id: string
  total_fields: number
  filled_count: number
  unfilled_count: number
  fields: FieldStatus[]
}

interface ProjectSummary {
  id: string
  project_name: string
  status: string
  clickup_list_id?: string
}

interface LetterSummary {
  template_key: string
  template_name: string
  total_fields: number
  filled_count: number
  unfilled_count: number
}

export function LegalLettersPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [selectedProject, setSelectedProject] = useState('')
  const [letters, setLetters] = useState<LetterSummary[]>([])
  const [previews, setPreviews] = useState<Record<string, TemplatePreview>>({})
  const [expanded, setExpanded] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, any>>({})
  const [municipality, setMunicipality] = useState('')

  useEffect(() => {
    api.projects.list()
      .then((list: ProjectSummary[]) => {
        const provisioned = list.filter(p => p.status === 'provisioned' || p.status === 'active')
        setProjects(provisioned)
        if (provisioned.length === 1) setSelectedProject(provisioned[0].id)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedProject) { setLetters([]); setPreviews({}); setMunicipality(''); return }
    api.legalLetters.forProject(selectedProject)
      .then(data => {
        setLetters(data.letters)
        setMunicipality(data.municipality)
      })
      .catch(() => setLetters([]))
  }, [selectedProject])

  const generate = async (templateKey: string) => {
    setGenerating(templateKey)
    try {
      const result = await api.legalLetters.pipeline(templateKey, selectedProject)
      setResults(prev => ({ ...prev, [templateKey]: result }))
      // Refresh preview
      const preview = await api.legalLetters.preview(selectedProject, templateKey).catch(() => null)
      if (preview) setPreviews(prev => ({ ...prev, [templateKey]: preview }))
    } catch (e: any) {
      setResults(prev => ({ ...prev, [templateKey]: { error: e.message } }))
    }
    setGenerating(null)
  }

  if (loading) return (
    <ModuleLayout module="legal-letters" activePage="overview">
      <Spinner size="lg" />
    </ModuleLayout>
  )

  return (
    <ModuleLayout module="legal-letters" activePage="overview">
      <div className="flex flex-col gap-6 max-w-3xl">
        <h2 className="text-lg font-semibold text-ws-fg">Legal Letters</h2>

        <div>
          <label className="text-xs font-medium text-ws-text-secondary uppercase tracking-wide block mb-1.5">
            Project
          </label>
          <select
            className="setting-input"
            value={selectedProject}
            onChange={e => { setSelectedProject(e.target.value); setResults({}) }}
            style={{ width: '100%', maxWidth: 400 }}
          >
            <option value="">Select a project</option>
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.project_name}</option>
            ))}
          </select>
        </div>

        {selectedProject && letters.length > 0 && (
          <Card padding="none">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-ws-panel-border text-left text-ws-text-secondary">
                  <th className="px-4 py-2.5 font-medium">Template</th>
                  <th className="px-4 py-2.5 font-medium">Fields</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {letters.map(letter => {
                  const key = letter.template_key
                  const preview = previews[key]
                  const isExpanded = expanded === key
                  const result = results[key]
                  return (
                    <TemplateRow
                      key={key}
                      letter={letter}
                      preview={preview}
                      expanded={isExpanded}
                      onToggle={() => {
                        if (!isExpanded && !preview) {
                          api.legalLetters.preview(selectedProject, key)
                            .then(p => setPreviews(prev => ({ ...prev, [key]: p })))
                            .catch(() => {})
                        }
                        setExpanded(isExpanded ? null : key)
                      }}
                      onGenerate={() => generate(key)}
                      generating={generating === key}
                      result={result}
                    />
                  )
                })}
              </tbody>
            </table>
          </Card>
        )}

        {selectedProject && letters.length === 0 && !loading && (
          <p className="text-sm text-ws-text-secondary">No applicable legal letters for this municipality</p>
        )}
      </div>
    </ModuleLayout>
  )
}

function TemplateRow({
  letter, preview, expanded, onToggle, onGenerate, generating, result,
}: {
  letter: LetterSummary
  preview?: TemplatePreview
  expanded: boolean
  onToggle: () => void
  onGenerate: () => void
  generating: boolean
  result?: any
}) {
  return (
    <>
      <tr
        className="border-b border-ws-panel-border cursor-pointer hover:bg-ws-bg-hover"
        onClick={onToggle}
      >
        <td className="px-4 py-2.5 font-medium text-ws-fg">{letter.template_name}</td>
        <td className="px-4 py-2.5">
          <span className="text-ws-text-secondary">
            {letter.filled_count}/{letter.total_fields} filled
          </span>
        </td>
        <td className="px-4 py-2.5">
          {letter.unfilled_count === 0
            ? <Badge variant="success">Complete</Badge>
            : <Badge variant="warning">{letter.unfilled_count} pending</Badge>
          }
        </td>
        <td className="px-4 py-2.5 text-right">
          <Button
            size="sm"
            variant="primary"
            onClick={e => { e.stopPropagation(); onGenerate() }}
            disabled={generating}
          >
            {generating ? 'Generating...' : 'Generate PDF'}
          </Button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={4} className="px-4 py-3 bg-ws-bg-subtle">
            <div className="flex flex-col gap-2">
              <table className="w-full text-xs">
                <tbody>
                  {preview.fields.map(f => (
                    <tr key={f.field} className="border-b border-ws-panel-border last:border-0">
                      <td className="py-1.5 pr-3 font-mono text-ws-text-secondary" style={{ width: 220 }}>
                        {f.field}
                      </td>
                      <td className="py-1.5 pr-3">
                        {f.filled
                          ? <span className="text-ws-fg">{f.value}</span>
                          : <span className="text-ws-text-disabled">PENDING</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result && !result.error && (
                <div className="text-xs text-ws-text-secondary mt-1 border-t border-ws-panel-border pt-2">
                  <p>Generated {result.pdf_filename} at {result.generated_at}</p>
                  {result.attachment && <p>Attached to ClickUp task</p>}
                  {result.subtasks_created?.length > 0 && (
                    <p>{result.subtasks_created.length} subtasks created for pending fields</p>
                  )}
                </div>
              )}
              {result?.error && (
                <p className="text-xs text-ws-error mt-1">{result.error}</p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
