import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { clsx } from 'clsx'
import { Upload, Plus, X, ChevronRight, Grid3X3 } from 'lucide-react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'
import type { PolicyMatrixData, PolicyTopic, CitySummary } from '@/lib/types'

const STAGE_NAMES: Record<number, string> = {
  1: 'Pre-PPAP Checklist',
  2: 'Preliminary Art Plan',
  3: 'Detailed Public Art Plan',
  5: 'Artist Selection',
  7: 'Artist Contract',
  8: 'Artwork Management',
  10: 'Installation',
  11: 'Final Documentation',
}

function slugToDisplayName(slug: string): string {
  const words = slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1))
  return words.join(' ')
}

export function PolicyMatrixPage() {
  const [matrix, setMatrix] = useState<PolicyMatrixData | null>(null)
  const [cities, setCities] = useState<CitySummary[]>([])
  const [loading, setLoading] = useState(true)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importPath, setImportPath] = useState('')
  const [collapsedStages, setCollapsedStages] = useState<Set<number>>(new Set())
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    Promise.all([
      api.projects.policyMatrix.get().catch(() => null),
      api.projects.cities().catch(() => []),
    ]).then(([m, c]) => {
      if (m) setMatrix(m)
      setCities(c)
      setLoading(false)
    })
  }, [])

  const cityIds = useMemo(() => {
    if (!matrix) return []
    const ids = new Set(cities.map(c => c.city_id))
    Object.keys(matrix.entries).forEach(id => ids.add(id))
    return Array.from(ids).sort()
  }, [matrix, cities])

  const cityName = useCallback((id: string) => {
    if (matrix?.city_names?.[id]) return matrix.city_names[id]
    const c = cities.find(c => c.city_id === id)
    if (c?.city_name) return c.city_name
    return slugToDisplayName(id)
  }, [cities, matrix])

  const topicsByStage = useMemo(() => {
    if (!matrix) return new Map<number, PolicyTopic[]>()
    const map = new Map<number, PolicyTopic[]>()
    const sorted = [...matrix.topics].sort((a, b) => a.order - b.order)
    for (const topic of sorted) {
      const stage = topic.stage || 0
      if (!map.has(stage)) map.set(stage, [])
      map.get(stage)!.push(topic)
    }
    return map
  }, [matrix])

  const toggleStage = (stage: number) => {
    setCollapsedStages(prev => {
      const next = new Set(prev)
      if (next.has(stage)) next.delete(stage)
      else next.add(stage)
      return next
    })
  }

  const handleCellChange = (cityId: string, topicId: string, text: string) => {
    if (!matrix) return
    setMatrix(prev => {
      if (!prev) return prev
      const entries = { ...prev.entries }
      if (text.trim()) {
        entries[cityId] = { ...(entries[cityId] ?? {}), [topicId]: text }
      } else {
        const city = { ...(entries[cityId] ?? {}) }
        delete city[topicId]
        if (Object.keys(city).length === 0) delete entries[cityId]
        else entries[cityId] = city
      }
      return { ...prev, entries }
    })

    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      api.projects.policyMatrix.updateEntry(cityId, topicId, text).catch(() => {
        setFeedback('Failed to save')
        setFeedbackErr(true)
      })
    }, 600)
  }

  const handleImport = async () => {
    if (!importPath.trim()) return
    setImporting(true)
    setFeedback('')
    try {
      const data = await api.projects.policyMatrix.importXlsx(importPath.trim())
      setMatrix(data)
      setFeedback(`Imported ${data.topics.length} topics, ${Object.keys(data.entries).length} cities`)
      setFeedbackErr(false)
      setImportPath('')
    } catch (e: any) {
      setFeedback(e.message ?? 'Import failed')
      setFeedbackErr(true)
    }
    setImporting(false)
  }

  const handleTopicLabelChange = (topicId: string, newLabel: string) => {
    if (!matrix) return
    const topics = matrix.topics.map(t =>
      t.id === topicId ? { ...t, label: newLabel } : t
    )
    setMatrix({ ...matrix, topics })
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      api.projects.policyMatrix.updateTopics(topics).catch(() => {
        setFeedback('Failed to save topics')
        setFeedbackErr(true)
      })
    }, 600)
  }

  const addTopic = (stage: number, label: string) => {
    if (!matrix || !label.trim()) return
    const maxOrder = matrix.topics.reduce((max, t) => Math.max(max, t.order), -1)
    const newTopic: PolicyTopic = {
      id: `s${stage}-new-${Date.now()}`,
      label: label.trim(),
      stage,
      maps_to: [],
      order: maxOrder + 1,
    }
    const topics = [...matrix.topics, newTopic]
    setMatrix({ ...matrix, topics })
    api.projects.policyMatrix.updateTopics(topics).catch(() => {
      setFeedback('Failed to add topic')
      setFeedbackErr(true)
    })
  }

  const deleteTopic = (topicId: string) => {
    if (!matrix) return
    const topics = matrix.topics.filter(t => t.id !== topicId)
    const entries = { ...matrix.entries }
    for (const cityId of Object.keys(entries)) {
      const city = { ...entries[cityId] }
      delete city[topicId]
      if (Object.keys(city).length === 0) delete entries[cityId]
      else entries[cityId] = city
    }
    const updated = { ...matrix, topics, entries }
    setMatrix(updated)
    api.projects.policyMatrix.save(updated).catch(() => {
      setFeedback('Failed to delete topic')
      setFeedbackErr(true)
    })
  }

  const stageNumbers = Array.from(topicsByStage.keys()).sort((a, b) => a - b)

  return (
    <ModuleLayout module="systems" activePage="policy-matrix">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {loading ? (
          <p className="not-configured">Loading...</p>
        ) : (
          <>
            {/* Import bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', border: '1px solid var(--border)', background: 'var(--bg)' }}>
              <Upload size={16} style={{ color: 'var(--fg-secondary)', flexShrink: 0 }} />
              <input
                type="text"
                className="setting-input"
                value={importPath}
                onChange={e => setImportPath(e.target.value)}
                placeholder="Path to xlsx file..."
                style={{ flex: 1 }}
                onKeyDown={e => { if (e.key === 'Enter') handleImport() }}
              />
              <button className="btn btn-sm btn-primary" onClick={handleImport} disabled={importing || !importPath.trim()}>
                {importing ? 'Importing...' : 'Import'}
              </button>
            </div>
            <FeedbackMessage message={feedback} isError={feedbackErr} />

            {/* Grid */}
            {matrix && matrix.topics.length > 0 ? (
              <div className="table-wrap" style={{ border: '1px solid var(--border)' }}>
                <table className="artist-table" style={{ fontSize: '12px' }}>
                  <thead>
                    <tr>
                      <th style={{ minWidth: 200, position: 'sticky', left: 0, zIndex: 2, background: 'var(--bg-surface)' }}>
                        Topic
                      </th>
                      {cityIds.map(id => (
                        <th key={id} style={{ minWidth: 200 }}>
                          {cityName(id)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stageNumbers.map(stage => (
                      <StageSection
                        key={stage}
                        stage={stage}
                        stageName={STAGE_NAMES[stage] ?? (stage === 0 ? 'Unmapped' : `Stage ${stage}`)}
                        topics={topicsByStage.get(stage) ?? []}
                        cityIds={cityIds}
                        entries={matrix.entries}
                        collapsed={collapsedStages.has(stage)}
                        onToggle={() => toggleStage(stage)}
                        onCellChange={handleCellChange}
                        onLabelChange={handleTopicLabelChange}
                        onAddTopic={(label) => addTopic(stage, label)}
                        onDeleteTopic={deleteTopic}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ border: '1px solid var(--border)', padding: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Grid3X3 size={16} style={{ color: 'var(--fg-secondary)' }} />
                <span className="not-configured">No policy matrix data. Import an xlsx file to get started.</span>
              </div>
            )}
          </>
        )}
      </div>
    </ModuleLayout>
  )
}

function StageSection({
  stage, stageName, topics, cityIds, entries, collapsed, onToggle,
  onCellChange, onLabelChange, onAddTopic, onDeleteTopic,
}: {
  stage: number
  stageName: string
  topics: PolicyTopic[]
  cityIds: string[]
  entries: Record<string, Record<string, string>>
  collapsed: boolean
  onToggle: () => void
  onCellChange: (cityId: string, topicId: string, text: string) => void
  onLabelChange: (topicId: string, label: string) => void
  onAddTopic: (label: string) => void
  onDeleteTopic: (topicId: string) => void
}) {
  const [addingTopic, setAddingTopic] = useState(false)
  const [newLabel, setNewLabel] = useState('')
  const addInputRef = useRef<HTMLInputElement>(null)
  const colCount = cityIds.length + 1

  const handleAddConfirm = () => {
    if (newLabel.trim()) {
      onAddTopic(newLabel.trim())
      setNewLabel('')
      setAddingTopic(false)
    }
  }

  useEffect(() => {
    if (addingTopic && addInputRef.current) addInputRef.current.focus()
  }, [addingTopic])

  return (
    <>
      {/* Stage header */}
      <tr onClick={onToggle} style={{ cursor: 'pointer' }}>
        <td colSpan={colCount} style={{
          padding: '8px 12px',
          background: 'var(--bg-surface)',
          borderBottom: '1px solid var(--border)',
          fontFamily: 'var(--font-sans)',
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ChevronRight
              size={14}
              className={clsx('transition-transform', !collapsed && 'rotate-90')}
              style={{ color: 'var(--fg-secondary)' }}
            />
            <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-secondary)' }}>
              {stageName}
            </span>
            <span style={{ fontSize: '11px', color: 'var(--fg-disabled)', fontWeight: 400 }}>
              ({topics.length})
            </span>
          </span>
        </td>
      </tr>

      {/* Topic rows */}
      {!collapsed && topics.map(topic => (
        <TopicRow
          key={topic.id}
          topic={topic}
          cityIds={cityIds}
          entries={entries}
          onCellChange={onCellChange}
          onLabelChange={onLabelChange}
          onDelete={() => onDeleteTopic(topic.id)}
        />
      ))}

      {/* Add topic row */}
      {!collapsed && (
        <tr>
          <td colSpan={colCount} style={{ padding: '4px 12px', borderBottom: '1px solid var(--border)' }}>
            {addingTopic ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  ref={addInputRef}
                  type="text"
                  className="edit-input"
                  value={newLabel}
                  onChange={e => setNewLabel(e.target.value)}
                  placeholder="Topic label..."
                  style={{ width: '240px', fontSize: '12px', padding: '3px 6px' }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleAddConfirm()
                    if (e.key === 'Escape') { setAddingTopic(false); setNewLabel('') }
                  }}
                  onBlur={() => {
                    if (!newLabel.trim()) { setAddingTopic(false); setNewLabel('') }
                  }}
                />
                <button
                  className="btn btn-sm btn-primary"
                  onMouseDown={e => { e.preventDefault(); handleAddConfirm() }}
                >
                  Add
                </button>
                <button
                  className="btn btn-sm btn-ghost"
                  onMouseDown={e => { e.preventDefault(); setAddingTopic(false); setNewLabel('') }}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                className="btn btn-sm btn-ghost"
                onClick={(e) => { e.stopPropagation(); setAddingTopic(true) }}
                style={{ fontSize: '11px', opacity: 0.7 }}
              >
                <Plus size={12} /> Add topic
              </button>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

function TopicRow({
  topic, cityIds, entries, onCellChange, onLabelChange, onDelete,
}: {
  topic: PolicyTopic
  cityIds: string[]
  entries: Record<string, Record<string, string>>
  onCellChange: (cityId: string, topicId: string, text: string) => void
  onLabelChange: (topicId: string, label: string) => void
  onDelete: () => void
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  const handleDelete = () => {
    if (confirmDelete) {
      onDelete()
    } else {
      setConfirmDelete(true)
      setTimeout(() => setConfirmDelete(false), 3000)
    }
  }

  return (
    <tr>
      <td style={{
        position: 'sticky', left: 0, zIndex: 1,
        background: 'var(--bg)',
        padding: '4px 12px', verticalAlign: 'top',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '4px' }}>
          <input
            type="text"
            value={topic.label}
            onChange={e => onLabelChange(topic.id, e.target.value)}
            className="edit-input"
            style={{ flex: 1, fontSize: '12px', padding: '2px 4px' }}
          />
          <button
            onClick={handleDelete}
            style={{
              flexShrink: 0, marginTop: '2px', padding: '2px',
              background: confirmDelete ? 'rgba(140, 74, 74, 0.1)' : 'none',
              border: 'none', borderRadius: '2px', cursor: 'pointer',
              color: confirmDelete ? 'var(--color-error)' : 'var(--fg-disabled)',
            }}
            title={confirmDelete ? 'Click again to confirm' : 'Delete topic'}
          >
            <X size={12} />
          </button>
        </div>
      </td>
      {cityIds.map(cityId => {
        const text = entries[cityId]?.[topic.id] ?? ''
        return (
          <td key={cityId} style={{ padding: '4px 8px', verticalAlign: 'top' }}>
            <PolicyCell
              value={text}
              onChange={val => onCellChange(cityId, topic.id, val)}
            />
          </td>
        )
      })}
    </tr>
  )
}

function PolicyCell({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)

  useEffect(() => { setDraft(value) }, [value])

  if (!editing) {
    return (
      <div
        onClick={() => setEditing(true)}
        style={{
          minHeight: 28, cursor: 'pointer', fontSize: '12px', lineHeight: 1.4,
          color: value ? 'var(--fg)' : 'var(--fg-disabled)',
          whiteSpace: 'pre-wrap', maxHeight: 80, overflow: 'hidden', padding: '2px 0',
        }}
        title={value || 'Click to edit'}
      >
        {value ? (value.length > 120 ? value.slice(0, 120) + '...' : value) : '\u2014'}
      </div>
    )
  }

  return (
    <textarea
      value={draft}
      onChange={e => setDraft(e.target.value)}
      onBlur={() => {
        setEditing(false)
        if (draft !== value) onChange(draft)
      }}
      autoFocus
      rows={4}
      className="edit-textarea edit-input"
      style={{ fontSize: '12px', lineHeight: 1.4 }}
    />
  )
}
