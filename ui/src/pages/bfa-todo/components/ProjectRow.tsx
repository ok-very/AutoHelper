import { useState } from 'react'
import { clsx } from 'clsx'
import { ChevronRight, Save, X, AlertTriangle, Check, Pencil } from 'lucide-react'
import { Badge } from '@ui/atoms'
import { api } from '@/lib/api'
import { IframeCompositionView } from './IframeCompositionView'
import type { BfaTodoProject } from '../types'

interface ProjectRowProps {
  project: BfaTodoProject
  isExpanded: boolean
  isSelected: boolean
  memberMap: Record<string, string>
  onToggleExpand: () => void
  onToggleSelect: () => void
  onProjectUpdated: () => void
}

function ProjectCompositionView({ uid, onProjectUpdated }: { uid: string; onProjectUpdated: () => void }) {
  return (
    <IframeCompositionView
      uid={uid}
      fetchUrl={`/api/bfa-todo/projects/${uid}/html`}
      onSaveSection={async (sectionName, html) => {
        await api.bfaTodo.updateSection(uid, sectionName, html)
        onProjectUpdated()
      }}
      title={`Project ${uid}`}
    />
  )
}

export function ProjectRow({
  project, isExpanded, isSelected, memberMap, onToggleExpand, onToggleSelect, onProjectUpdated,
}: ProjectRowProps) {
  const leadTitle = memberMap[project.owner_team] || project.owner_team
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editFields, setEditFields] = useState({
    client: project.client,
    project_name: project.project_name,
    city: project.city,
    phase: project.phase,
    owner_team: project.owner_team,
  })

  const hasIssues = project.validation && (project.validation.error_count > 0 || project.validation.warning_count > 0)
  const hasErrors = project.validation && project.validation.error_count > 0
  const suggestions = project.validation?.items.filter(i => i.suggestion) ?? []

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditFields({
      client: project.client,
      project_name: project.project_name,
      city: project.city,
      phase: project.phase,
      owner_team: project.owner_team,
    })
    setEditing(true)
  }

  const cancelEdit = () => setEditing(false)

  const saveEdit = async () => {
    setSaving(true)
    try {
      const changes: Record<string, string> = {}
      if (editFields.client !== project.client) changes.client = editFields.client
      if (editFields.project_name !== project.project_name) changes.project_name = editFields.project_name
      if (editFields.city !== project.city) changes.city = editFields.city
      if (editFields.phase !== project.phase) changes.phase = editFields.phase
      if (editFields.owner_team !== project.owner_team) changes.owner_team = editFields.owner_team
      if (Object.keys(changes).length > 0) {
        await api.bfaTodo.updateProject(project.uid, changes)
        onProjectUpdated()
      }
      setEditing(false)
    } catch {
      // stay in edit mode
    } finally {
      setSaving(false)
    }
  }

  const applySuggestion = (field: string, value: string) => {
    setEditFields(prev => ({ ...prev, [field]: value }))
  }

  if (editing) {
    return (
      <div style={{ borderBottom: '1px solid var(--border)', background: 'rgba(63, 92, 110, 0.06)', fontFamily: 'var(--font-sans)' }}>
        <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="flex items-center gap-2">
            <input
              type="text"
              className="setting-input"
              value={editFields.client}
              onChange={e => setEditFields(prev => ({ ...prev, client: e.target.value }))}
              placeholder="Client"
              style={{ fontSize: '12px', width: '180px', fontWeight: 600 }}
            />
            <span style={{ color: 'var(--fg-secondary)', fontSize: '13px' }}>—</span>
            <input
              type="text"
              className="setting-input"
              value={editFields.project_name}
              onChange={e => setEditFields(prev => ({ ...prev, project_name: e.target.value }))}
              placeholder="Project name"
              style={{ fontSize: '12px', flex: 1, fontWeight: 600 }}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              className="setting-input"
              value={editFields.city}
              onChange={e => setEditFields(prev => ({ ...prev, city: e.target.value }))}
              placeholder="City"
              style={{ fontSize: '12px', width: '140px' }}
            />
            <input
              type="text"
              className="setting-input"
              value={editFields.phase}
              onChange={e => setEditFields(prev => ({ ...prev, phase: e.target.value }))}
              placeholder="Phase"
              style={{ fontSize: '12px', width: '140px' }}
            />
            <input
              type="text"
              className="setting-input"
              value={editFields.owner_team}
              onChange={e => setEditFields(prev => ({ ...prev, owner_team: e.target.value }))}
              placeholder="Team"
              style={{ fontSize: '12px', width: '80px' }}
            />
            <div style={{ flex: 1 }} />
            <button className="btn btn-sm btn-primary" onClick={saveEdit} disabled={saving} style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}>
              <Save size={11} /> {saving ? 'Saving...' : 'Save'}
            </button>
            <button className="btn btn-sm" onClick={cancelEdit} disabled={saving} style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}>
              <X size={11} /> Cancel
            </button>
          </div>
          {suggestions.length > 0 && (
            <div className="flex flex-wrap items-center gap-2" style={{ fontSize: '11px' }}>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className="btn btn-sm"
                  onClick={() => applySuggestion(s.field, s.suggestion!)}
                  style={{ fontSize: '11px', padding: '1px 6px', gap: 3, display: 'flex', alignItems: 'center', color: 'var(--color-warning, #b45309)' }}
                >
                  <Check size={10} /> {s.message}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ borderBottom: '1px solid var(--border)', background: isExpanded ? 'rgba(63, 92, 110, 0.04)' : undefined }}>
      <div
        className="flex items-center gap-2"
        style={{ padding: '6px 12px', cursor: 'pointer', fontFamily: 'var(--font-sans)', opacity: project.status === 'on_hold' ? 0.55 : 1 }}
        onClick={onToggleExpand}
      >
        <input
          type="checkbox"
          checked={isSelected}
          onChange={e => { e.stopPropagation(); onToggleSelect() }}
          onClick={e => e.stopPropagation()}
          style={{ accentColor: 'var(--accent)' }}
        />
        <ChevronRight
          size={14}
          className={clsx('transition-transform shrink-0', isExpanded && 'rotate-90')}
          style={{ color: 'var(--fg-secondary)' }}
        />
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--fg)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {project.client} — {project.project_name}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <span style={{ fontSize: '11px', color: 'var(--fg-secondary)', minWidth: 80, textAlign: 'right' }}>{project.city}</span>
          <span style={{ width: 1, height: 12, background: 'var(--border)' }} />
          <Badge variant="phase" size="xs">{project.phase}</Badge>
          <Badge variant="neutral" size="xs">{project.owner_team}</Badge>
          {project.status === 'on_hold' && <Badge variant="neutral" size="xs">ON HOLD</Badge>}
          {hasIssues ? (
            <button
              onClick={startEdit}
              title={project.validation.items.map(i => i.message).join('\n')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex' }}
            >
              <AlertTriangle size={14} style={{ color: hasErrors ? 'var(--color-error, #dc2626)' : 'var(--color-warning, #b45309)' }} />
            </button>
          ) : (
            <button
              onClick={startEdit}
              title="Edit fields"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', opacity: 0.3 }}
            >
              <Pencil size={12} style={{ color: 'var(--fg-secondary)' }} />
            </button>
          )}
        </div>
      </div>
      {isExpanded && <ProjectCompositionView uid={project.uid} onProjectUpdated={onProjectUpdated} />}
    </div>
  )
}
