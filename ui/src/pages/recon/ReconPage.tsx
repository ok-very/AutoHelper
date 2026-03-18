import { useState, useEffect, useCallback } from 'react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { CssSpinner } from '@/components/CssSpinner'
import { CategoryBadge } from '@/components/CategoryBadge'
import { api } from '@/lib/api'
import { capitalize } from '@/lib/helpers'
import type {
  ReconciliationData,
  AdminFile,
  ReconOrphan,
  ReconStalled,
  ReconFuzzy,
  ReconPanelGap,
  ReconDuplicate,
  ReconVariant,
  ReconAliasConflict,
} from '@/lib/types'

type TabKey = keyof ReconciliationData | 'unattributed_files'

const ENGAGEMENT_TABS: { key: TabKey; label: string; countId: string }[] = [
  { key: 'orphan_eois', label: 'Orphan EOIs', countId: 'eois' },
  { key: 'orphan_proposals', label: 'Orphan Proposals', countId: 'proposals' },
  { key: 'stalled_projects', label: 'Stalled', countId: 'stalled' },
  { key: 'fuzzy_matches', label: 'Fuzzy Matches', countId: 'fuzzy' },
  { key: 'panel_gaps', label: 'Panel Gaps', countId: 'panels' },
]

const QUALITY_TABS: { key: TabKey; label: string; countId: string }[] = [
  { key: 'duplicate_artists', label: 'Duplicate Names', countId: 'dupes' },
  { key: 'affiliation_variants', label: 'Affiliation Variants', countId: 'affs' },
  { key: 'identity_inconsistencies', label: 'Identity Dupes', countId: 'ids' },
  { key: 'alias_conflicts', label: 'Alias Conflicts', countId: 'aliases' },
  { key: 'location_variants', label: 'Location Variants', countId: 'locs' },
]

function artistLink(id: string, name: string) {
  return (
    <span className="recon-name">
      <a className="clickable-name" href={`/artists-dashboard#${encodeURIComponent(id)}`}>{name}</a>
    </span>
  )
}

export function ReconPage() {
  const [reconData, setReconData] = useState<ReconciliationData | null>(null)
  const [adminFiles, setAdminFiles] = useState<AdminFile[]>([])
  const [activeTab, setActiveTab] = useState<TabKey>('orphan_eois')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      const [r, a] = await Promise.all([
        api.artists.reconciliation().catch(() => null),
        api.artists.adminFiles().catch(() => []),
      ])
      if (r) setReconData(r)
      else setError(true)
      setAdminFiles(a)
    } catch {
      setError(true)
    }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const reconAction = async (action: string, artistId: string, projectName: string, projectIndex?: number, newStatus?: string) => {
    const body: Record<string, unknown> = { action, artist_id: artistId }
    if (projectName) { body.project_name = projectName; body.eoi_name = projectName }
    if (projectIndex !== undefined) body.project_index = projectIndex
    if (newStatus) body.new_status = newStatus
    await api.artists.resolveRecon(body)
    load()
  }

  const mergeValues = async (action: string, oldValue: string, newValue: string) => {
    await api.artists.resolveRecon({ action, old_value: oldValue, new_value: newValue })
    load()
  }

  const attributeFile = async (fileId: string, artistId: string) => {
    await api.artists.attributeFile(fileId, artistId)
    load()
  }

  const attributeFileSearch = async (fileId: string) => {
    const query = prompt('Search for artist name:')
    if (!query) return
    try {
      const res = await fetch(`/artists?q=${encodeURIComponent(query)}&limit=10`)
      const artists = await res.json()
      if (!artists.length) { alert('No artists found for: ' + query); return }
      const choices = artists.map((a: { display_name: string; artist_id: string }, i: number) =>
        `${i + 1}. ${a.display_name} (${a.artist_id})`
      ).join('\n')
      const pick = prompt('Select artist:\n' + choices + '\n\nEnter number:')
      if (!pick) return
      const idx = parseInt(pick, 10) - 1
      if (idx >= 0 && idx < artists.length) {
        await attributeFile(fileId, artists[idx].artist_id)
      }
    } catch { /* ignore */ }
  }

  function getCount(key: TabKey): number {
    if (key === 'unattributed_files') return adminFiles.length
    return (reconData?.[key as keyof ReconciliationData] as unknown[] ?? []).length
  }

  return (
    <ModuleLayout module="artist-directory" activePage="recon">

      <header className="header">
        <h1>Reconciliation</h1>
        <div className="header-actions">
          <button className="btn btn-ghost" onClick={load}>&#x27F3; Reload</button>
        </div>
      </header>

      {loading && (
        <div className="loading-center">
          <CssSpinner size="lg" />
          Loading reconciliation data…
        </div>
      )}

      {error && !loading && (
        <div className="loading-center">
          <p style={{ color: 'var(--color-error)' }}>Failed to load reconciliation data.</p>
          <button className="btn" onClick={load}>Retry</button>
        </div>
      )}

      {!loading && !error && <div className="health-card full-width" style={{ marginBottom: '16px' }}>
        <h3>Engagement Pipeline</h3>
        <TabBar tabs={ENGAGEMENT_TABS} active={activeTab} onSelect={setActiveTab} getCount={getCount} />

        <p style={{ fontSize: '11px', color: 'var(--fg-disabled)', margin: '8px 0' }}>Data quality</p>
        <TabBar tabs={QUALITY_TABS} active={activeTab} onSelect={setActiveTab} getCount={getCount} />

        <p style={{ fontSize: '11px', color: 'var(--fg-disabled)', margin: '8px 0' }}>Unattributed</p>
        <TabBar
          tabs={[{ key: 'unattributed_files' as TabKey, label: 'Unattributed Files', countId: 'unattributed' }]}
          active={activeTab}
          onSelect={setActiveTab}
          getCount={getCount}
        />

        <div>
          <TabContent
            tab={activeTab}
            reconData={reconData}
            adminFiles={adminFiles}
            reconAction={reconAction}
            mergeValues={mergeValues}
            attributeFile={attributeFile}
            attributeFileSearch={attributeFileSearch}
            reload={load}
          />
        </div>
      </div>}
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Tab Bar
// ---------------------------------------------------------------------------

function TabBar({ tabs, active, onSelect, getCount }: {
  tabs: { key: TabKey; label: string; countId: string }[]
  active: TabKey
  onSelect: (key: TabKey) => void
  getCount: (key: TabKey) => number
}) {
  return (
    <div className="recon-tabs">
      {tabs.map(t => (
        <button
          key={t.key}
          className={`recon-tab${t.key === active ? ' active' : ''}`}
          onClick={() => onSelect(t.key)}
        >
          {t.label} <span className="recon-count">{getCount(t.key)}</span>
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab Content Router
// ---------------------------------------------------------------------------

function TabContent({ tab, reconData, adminFiles, reconAction, mergeValues, attributeFile, attributeFileSearch, reload }: {
  tab: TabKey
  reconData: ReconciliationData | null
  adminFiles: AdminFile[]
  reconAction: (action: string, artistId: string, projectName: string, projectIndex?: number, newStatus?: string) => void
  mergeValues: (action: string, oldValue: string, newValue: string) => void
  attributeFile: (fileId: string, artistId: string) => void
  attributeFileSearch: (fileId: string) => void
  reload: () => void
}) {
  if (!reconData && tab !== 'unattributed_files') return <p className="empty">Loading...</p>

  switch (tab) {
    case 'orphan_eois': return <OrphanList items={reconData!.orphan_eois} reconAction={reconAction} />
    case 'orphan_proposals': return <OrphanList items={reconData!.orphan_proposals} reconAction={reconAction} showDeveloper />
    case 'stalled_projects': return <StalledList items={reconData!.stalled_projects} reconAction={reconAction} />
    case 'fuzzy_matches': return <FuzzyList items={reconData!.fuzzy_matches} reconAction={reconAction} />
    case 'panel_gaps': return <PanelGapList items={reconData!.panel_gaps} />
    case 'duplicate_artists': return <DuplicateList items={reconData!.duplicate_artists} onMerge={reload} />
    case 'affiliation_variants': return <VariantList items={reconData!.affiliation_variants} actionType="merge_affiliation" mergeValues={mergeValues} reconAction={reconAction} />
    case 'identity_inconsistencies': return <VariantList items={reconData!.identity_inconsistencies} actionType="merge_identity" mergeValues={mergeValues} reconAction={reconAction} />
    case 'alias_conflicts': return <AliasConflictList items={reconData!.alias_conflicts} onAction={reload} />
    case 'location_variants': return <VariantList items={reconData!.location_variants} actionType="merge_location" mergeValues={mergeValues} reconAction={reconAction} />
    case 'unattributed_files': return <UnattributedList items={adminFiles} attributeFile={attributeFile} attributeFileSearch={attributeFileSearch} />
    default: return <p className="empty">Unknown tab</p>
  }
}

// ---------------------------------------------------------------------------
// Engagement renderers
// ---------------------------------------------------------------------------

function OrphanList({ items, reconAction, showDeveloper }: {
  items: ReconOrphan[]
  reconAction: (action: string, artistId: string, projectName: string) => void
  showDeveloper?: boolean
}) {
  if (!items.length) return <p className="empty">No items</p>
  return (
    <>
      {items.map((item, i) => (
        <div key={i} className="recon-item">
          {artistLink(item.artist_id, item.display_name)}
          <span className="recon-meta">
            {item.project_name}
            {showDeveloper && item.developer ? ` — ${item.developer}` : ''}
          </span>
          <button className="btn btn-sm btn-primary" onClick={() => reconAction('link_eoi', item.artist_id, item.project_name)}>Link</button>
          <button className="btn btn-sm" onClick={() => reconAction('dismiss', item.artist_id, '')}>Dismiss</button>
        </div>
      ))}
    </>
  )
}

function StalledList({ items, reconAction }: {
  items: ReconStalled[]
  reconAction: (action: string, artistId: string, projectName: string, projectIndex?: number, newStatus?: string) => void
}) {
  if (!items.length) return <p className="empty">No items</p>
  return (
    <>
      {items.map((item, i) => (
        <div key={i} className="recon-item">
          {artistLink(item.artist_id, item.display_name)}
          <span className="recon-meta">{item.project_name} [{item.status}]</span>
          <button className="btn btn-sm btn-primary" onClick={() => reconAction('advance_status', item.artist_id, '', item.project_index, 'completed')}>Complete</button>
          <button className="btn btn-sm" onClick={() => reconAction('dismiss', item.artist_id, '')}>Dismiss</button>
        </div>
      ))}
    </>
  )
}

function FuzzyList({ items, reconAction }: {
  items: ReconFuzzy[]
  reconAction: (action: string, artistId: string, projectName: string) => void
}) {
  if (!items.length) return <p className="empty">No items</p>
  return (
    <>
      {items.map((item, i) => (
        <div key={i} className="recon-item">
          {artistLink(item.artist_id, item.display_name)}
          <span className="recon-meta">{item.source_name} &rarr; {item.match_name}</span>
          <span className="recon-match-score">{Math.round(item.score * 100)}%</span>
          <button className="btn btn-sm btn-primary" onClick={() => reconAction('link_eoi', item.artist_id, item.source_name)}>Link</button>
          <button className="btn btn-sm" onClick={() => reconAction('dismiss', item.artist_id, '')}>Dismiss</button>
        </div>
      ))}
    </>
  )
}

function PanelGapList({ items }: { items: ReconPanelGap[] }) {
  if (!items.length) return <p className="empty">No items</p>
  return (
    <>
      {items.map((item, i) => (
        <div key={i} className="recon-item">
          {artistLink(item.artist_id, item.display_name)}
          <span className="recon-meta">{item.panel_count} panel(s), no projects</span>
        </div>
      ))}
    </>
  )
}

// ---------------------------------------------------------------------------
// Data quality renderers
// ---------------------------------------------------------------------------

function DuplicateList({ items, onMerge }: { items: ReconDuplicate[]; onMerge: () => void }) {
  const [dismissed, setDismissed] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem('dismissed_pairs')
      return raw ? new Set(JSON.parse(raw)) : new Set()
    } catch { return new Set() }
  })
  const [merging, setMerging] = useState<string | null>(null)
  const [autoMergePreview, setAutoMergePreview] = useState<{ pairs: { keep_name: string; remove_name: string; score: number; keep_completeness: number; remove_completeness: number }[]; merged: number; errors: string[] } | null>(null)
  const [autoMerging, setAutoMerging] = useState(false)

  const dismiss = (idA: string, idB: string) => {
    const key = [idA, idB].sort().join('|')
    const next = new Set(dismissed)
    next.add(key)
    setDismissed(next)
    localStorage.setItem('dismissed_pairs', JSON.stringify([...next]))
  }

  const doMerge = async (keepId: string, removeId: string) => {
    setMerging(`${keepId}-${removeId}`)
    try {
      await api.artists.merge(keepId, removeId)
      onMerge()
    } catch (e) {
      alert(`Merge failed: ${e}`)
    }
    setMerging(null)
  }

  const previewAutoMerge = async () => {
    setAutoMerging(true)
    try {
      const result = await api.artists.autoMerge(0.95, true)
      setAutoMergePreview(result)
    } catch (e) {
      alert(`Auto-merge preview failed: ${e}`)
    }
    setAutoMerging(false)
  }

  const applyAutoMerge = async () => {
    setAutoMerging(true)
    try {
      await api.artists.autoMerge(0.95, false)
      setAutoMergePreview(null)
      onMerge()
    } catch (e) {
      alert(`Auto-merge failed: ${e}`)
    }
    setAutoMerging(false)
  }

  const highConfCount = items.filter(i => i.score >= 0.95).length
  const visible = items.filter(i => {
    const key = [i.artist_id_a, i.artist_id_b].sort().join('|')
    return !dismissed.has(key)
  })

  if (!items.length) return <p className="empty">No items</p>

  return (
    <>
      {highConfCount > 0 && (
        <div className="recon-item" style={{ background: 'var(--surface-raised)', borderRadius: '6px', padding: '8px 12px', marginBottom: '8px' }}>
          <span style={{ fontWeight: 600 }}>{highConfCount} high-confidence pair{highConfCount > 1 ? 's' : ''} (&ge;95%)</span>
          {!autoMergePreview ? (
            <button className="btn btn-sm" onClick={previewAutoMerge} disabled={autoMerging} style={{ marginLeft: '12px' }}>
              {autoMerging ? 'Loading\u2026' : 'Preview auto-merge'}
            </button>
          ) : (
            <>
              <span style={{ marginLeft: '12px', fontSize: '12px', color: 'var(--fg-secondary)' }}>
                Will merge {autoMergePreview.pairs.length} pairs
              </span>
              <button className="btn btn-sm btn-primary" onClick={applyAutoMerge} disabled={autoMerging} style={{ marginLeft: '8px' }}>
                {autoMerging ? 'Merging\u2026' : 'Apply'}
              </button>
              <button className="btn btn-sm" onClick={() => setAutoMergePreview(null)} style={{ marginLeft: '4px' }}>Cancel</button>
            </>
          )}
        </div>
      )}
      {autoMergePreview && autoMergePreview.pairs.length > 0 && (
        <div style={{ fontSize: '12px', marginBottom: '8px', padding: '4px 12px', background: 'var(--surface-sunken)', borderRadius: '4px' }}>
          {autoMergePreview.pairs.map((p, i) => (
            <div key={i}>Keep <strong>{p.keep_name}</strong> ({Math.round(p.keep_completeness * 100)}%) &larr; {p.remove_name} ({Math.round(p.remove_completeness * 100)}%)</div>
          ))}
        </div>
      )}
      {visible.map((item, i) => (
        <div key={i} className="recon-item">
          <a className="clickable-name" href={`/artists-dashboard#${encodeURIComponent(item.artist_id_a)}`}>{item.name_a}</a>
          <span className="recon-meta">&harr;</span>
          <a className="clickable-name" href={`/artists-dashboard#${encodeURIComponent(item.artist_id_b)}`}>{item.name_b}</a>
          <span className="recon-match-score">{Math.round(item.score * 100)}%</span>
          <button
            className="btn btn-sm btn-primary"
            disabled={merging !== null}
            onClick={() => doMerge(item.artist_id_a, item.artist_id_b)}
          >Keep "{item.name_a}"</button>
          <button
            className="btn btn-sm"
            disabled={merging !== null}
            onClick={() => doMerge(item.artist_id_b, item.artist_id_a)}
          >Keep "{item.name_b}"</button>
          <button className="btn btn-sm" onClick={() => dismiss(item.artist_id_a, item.artist_id_b)}>Not Dupes</button>
        </div>
      ))}
    </>
  )
}

function VariantList({ items, actionType, mergeValues, reconAction }: {
  items: ReconVariant[]
  actionType: string
  mergeValues: (action: string, oldValue: string, newValue: string) => void
  reconAction: (action: string, artistId: string, projectName: string) => void
}) {
  if (!items.length) return <p className="empty">No items</p>
  return (
    <>
      {items.map((item, i) => (
        <div key={i} className="recon-item">
          <span className="recon-name">
            {item.value_a} <span style={{ color: 'var(--fg-disabled)', fontSize: '11px' }}>({item.count_a})</span>
          </span>
          <span className="recon-meta">&harr;</span>
          <span className="recon-name">
            {item.value_b} <span style={{ color: 'var(--fg-disabled)', fontSize: '11px' }}>({item.count_b})</span>
          </span>
          <span className="recon-match-score">{Math.round(item.score * 100)}%</span>
          <button className="btn btn-sm btn-primary" onClick={() => mergeValues(actionType, item.value_b, item.value_a)}>Keep "{item.value_a}"</button>
          <button className="btn btn-sm" onClick={() => mergeValues(actionType, item.value_a, item.value_b)}>Keep "{item.value_b}"</button>
          <button className="btn btn-sm" onClick={() => reconAction('dismiss', '', '')}>Dismiss</button>
        </div>
      ))}
    </>
  )
}

function AliasConflictList({ items, onAction }: { items: ReconAliasConflict[]; onAction: () => void }) {
  const [selected, setSelected] = useState<Record<number, string>>({})
  const [acting, setActing] = useState(false)

  const assignAlias = async (idx: number, item: ReconAliasConflict) => {
    const toArtistId = selected[idx]
    if (!toArtistId) return
    setActing(true)
    try {
      // Remove from all others, assign to selected
      for (const a of item.artists) {
        if (a.artist_id !== toArtistId) {
          await api.artists.resolveRecon({
            action: 'assign_alias',
            from_artist_id: a.artist_id,
            to_artist_id: toArtistId,
            name: item.shared_name,
          })
          break // Only need to move from one — they all share the same name
        }
      }
      onAction()
    } catch (e) {
      alert(`Assign failed: ${e}`)
    }
    setActing(false)
  }

  const removeFromAll = async (item: ReconAliasConflict) => {
    setActing(true)
    try {
      for (const a of item.artists) {
        await api.artists.resolveRecon({
          action: 'remove_alias',
          artist_id: a.artist_id,
          name: item.shared_name,
        })
      }
      onAction()
    } catch (e) {
      alert(`Remove failed: ${e}`)
    }
    setActing(false)
  }

  if (!items.length) return <p className="empty">No items</p>
  return (
    <>
      {items.map((item, i) => (
        <div key={i} className="recon-item" style={{ flexWrap: 'wrap' }}>
          <span className="recon-name" style={{ fontWeight: 600 }}>{item.shared_name}</span>
          <span className="recon-meta" style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            {item.artists.map((a) => (
              <label key={a.artist_id} style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                <input
                  type="radio"
                  name={`alias-${i}`}
                  checked={selected[i] === a.artist_id}
                  onChange={() => setSelected(prev => ({ ...prev, [i]: a.artist_id }))}
                />
                <a className="clickable-name" href={`/artists-dashboard#${encodeURIComponent(a.artist_id)}`}>{a.display_name}</a>
                <span style={{ fontSize: '11px', color: 'var(--fg-disabled)' }}>({a.type})</span>
              </label>
            ))}
          </span>
          <button
            className="btn btn-sm btn-primary"
            disabled={acting || !selected[i]}
            onClick={() => assignAlias(i, item)}
          >Assign</button>
          <button
            className="btn btn-sm"
            disabled={acting}
            onClick={() => removeFromAll(item)}
          >Remove from all</button>
        </div>
      ))}
    </>
  )
}

// ---------------------------------------------------------------------------
// Unattributed files
// ---------------------------------------------------------------------------

function UnattributedList({ items, attributeFile, attributeFileSearch }: {
  items: AdminFile[]
  attributeFile: (fileId: string, artistId: string) => void
  attributeFileSearch: (fileId: string) => void
}) {
  if (!items.length) return <p className="empty">No unattributed files</p>
  return (
    <table className="ranking-table">
      <thead>
        <tr>
          <th>File</th>
          <th>Folder</th>
          <th>Category</th>
          <th>Type</th>
          <th>Candidate</th>
          <th>Score</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {items.map(f => (
          <tr key={f.file_id}>
            <td title={f.file_path} style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {f.file_name}
            </td>
            <td>{f.folder_name}</td>
            <td><CategoryBadge category={f.category} /></td>
            <td style={{ fontSize: '11px' }}>{f.file_type}</td>
            <td>
              {f.candidate_display_name ? (
                <a className="clickable-name" href={`/artists-dashboard#${encodeURIComponent(f.candidate_artist_id!)}`}>
                  {f.candidate_display_name}
                </a>
              ) : (
                <span style={{ color: 'var(--fg-disabled)' }}>None</span>
              )}
            </td>
            <td>{f.match_score ? `${Math.round(f.match_score * 100)}%` : '—'}</td>
            <td style={{ whiteSpace: 'nowrap' }}>
              {f.candidate_artist_id && (
                <button className="btn btn-sm btn-primary" onClick={() => attributeFile(f.file_id, f.candidate_artist_id!)}>Accept</button>
              )}{' '}
              <button className="btn btn-sm" onClick={() => attributeFileSearch(f.file_id)}>Search</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
