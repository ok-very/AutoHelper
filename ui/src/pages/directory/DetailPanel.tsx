import { useState, useRef } from 'react'
import { ScoreBar } from '@/components/ScoreBar'
import { GapPills } from '@/components/GapPills'
import { CategoryBadge } from '@/components/CategoryBadge'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'
import { capitalize, basename } from '@/lib/helpers'
import { ICO } from './icons'
import type { ArtistManifest, DocumentEntry } from '@/lib/types'

interface DetailPanelProps {
  manifest: ArtistManifest
  bioText: string
  onClose: () => void
  onRefresh: () => void
}

export function DetailPanel({ manifest: m, bioText, onClose, onRefresh }: DetailPanelProps) {
  const id = m.identity
  const tags = id.identity_tags
  const contact = m.contact
  const docs = m.documents
  const eng = m.engagement
  const img = m.images
  const comp = m.completeness
  const ai = m.ai_enrichment
  const notes = m._review_notes ?? []
  const fls = m.folder_locations ?? []

  // Editable fields
  const [displayName, setDisplayName] = useState(id.display_name ?? '')
  const [pronouns, setPronouns] = useState(id.pronouns ?? '')
  const [careerStage, setCareerStage] = useState(id.career_stage ?? '')
  const [email, setEmail] = useState(contact.email ?? '')
  const [phone, setPhone] = useState(contact.phone ?? '')
  const [website, setWebsite] = useState(contact.website ?? '')
  const [contactNotes, setContactNotes] = useState(contact.notes ?? '')
  const [saveFeedback, setSaveFeedback] = useState('')
  const [saveErr, setSaveErr] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showPanelForm, setShowPanelForm] = useState(false)
  const [showProjectForm, setShowProjectForm] = useState(false)

  const openFile = (path: string) => { if (path) api.artists.openFile(path) }
  const openFolder = () => api.artists.openFolder(m.artist_id)
  const openFolderPath = (path: string) => { if (path) api.artists.openFile(path) }

  const resolveNote = async (index: number) => {
    await api.artists.resolveNote(m.artist_id, index)
    onRefresh()
  }

  const rescan = async () => {
    await api.artists.rescan(m.artist_id)
    onRefresh()
  }

  const saveChanges = async () => {
    setSaving(true)
    setSaveFeedback('Saving\u2026')
    setSaveErr(false)
    try {
      const r = await api.artists.saveManifest(m.artist_id, {
        identity: {
          display_name: displayName,
          pronouns: pronouns || null,
          career_stage: (careerStage || null) as ArtistManifest['identity']['career_stage'],
        },
        contact: {
          email: email || null,
          phone: phone || null,
          website: website || null,
          notes: contactNotes || null,
        },
      })
      if (r.ok) { setSaveFeedback('\u2713 Saved'); setSaveErr(false); onRefresh() }
      else { setSaveFeedback('\u2717 Error'); setSaveErr(true) }
    } catch {
      setSaveFeedback('\u2717 Network error')
      setSaveErr(true)
    }
    setSaving(false)
  }

  // Typed names
  const namesByType: Record<string, string[]> = {}
  ;(id.names ?? []).forEach(n => { (namesByType[n.type] = namesByType[n.type] ?? []).push(n.name) })

  // Affiliations by type
  const affsByType: Record<string, string[]> = {}
  ;(tags.affiliations ?? []).forEach(a => { (affsByType[a.type] = affsByType[a.type] ?? []).push(a.name) })

  // Locations by type
  const locsByType: Record<string, string[]> = {}
  ;(tags.locations ?? []).forEach(l => { (locsByType[l.type] = locsByType[l.type] ?? []).push(l.place) })

  const statusColors: Record<string, string> = {
    submitted: 'var(--fg-secondary)', longlisted: 'var(--color-warning)',
    shortlisted: 'var(--accent)', awarded: 'var(--color-success)', completed: 'var(--cat-indigenous)',
  }

  return (
    <>
      <div className="detail-overlay" onClick={onClose} />
      <aside className="detail-panel">
        <div className="detail-header">
          <span className="detail-title">{id.display_name ?? m.artist_id}</span>
          <button className="detail-close" onClick={onClose}>&times;</button>
        </div>
        <div className="detail-body">
          {/* Completeness */}
          <div className="detail-section">
            <ScoreBar score={comp.score} variant="detail" />
            <GapPills gaps={comp.gaps ?? []} />
          </div>

          {/* Review notes */}
          {notes.length > 0 && (
            <div className="detail-section">
              <h3>Review Notes</h3>
              {notes.map((n, i) => (
                <div key={i} className="review-note">
                  <span>{n}</span>
                  <button className="btn btn-sm" onClick={() => resolveNote(i)}>Resolve</button>
                </div>
              ))}
            </div>
          )}

          {/* AI enrichment */}
          {ai && (
            <div className="detail-section ai-section">
              <h3>
                AI Enrichment
                <span className={`ai-confidence ai-${ai.confidence ?? 'med'}`}>{capitalize(ai.confidence ?? 'medium')}</span>
                <span className="ai-model">{ai.model ?? ''}</span>
              </h3>
              {ai.bio_summary && <div className="ai-text">{ai.bio_summary}</div>}
              {ai.medium && <div style={{ fontSize: '13px', margin: '4px 0' }}><strong>Medium:</strong> {ai.medium}</div>}
              {ai.website && <div style={{ fontSize: '13px' }}><strong>Website:</strong> <a href={ai.website} target="_blank" style={{ color: 'var(--accent)' }}>{ai.website}</a></div>}
              <div className="ai-disclaimer">AI-generated — verify before publishing</div>
            </div>
          )}

          {/* Identity (editable) */}
          <div className="detail-section">
            <h3>Identity</h3>
            <EditRow label="Name" value={displayName} onChange={setDisplayName} />
            <EditRow label="Pronouns" value={pronouns} onChange={setPronouns} placeholder="e.g. she/her" missing={!pronouns} />
            <div className="edit-row">
              <span className="edit-label">Career Stage</span>
              <select className="edit-input" value={careerStage} onChange={e => setCareerStage((e.target as HTMLSelectElement).value)}>
                <option value="">—</option>
                <option value="emerging">Emerging</option>
                <option value="mid-career">Mid-career</option>
                <option value="established">Established</option>
              </select>
            </div>

            {namesByType.traditional && <ReadRow label="Traditional" value={namesByType.traditional.join(', ')} />}
            {namesByType.pseudonym && <ReadRow label="Also" value={namesByType.pseudonym.join(', ')} secondary />}
            {namesByType.studio && <ReadRow label="Studio" value={namesByType.studio.join(', ')} secondary />}
            {namesByType.trade && <ReadRow label="Trade" value={namesByType.trade.join(', ')} secondary />}

            {affsByType.nation && <ReadRow label="Nations" value={affsByType.nation.join(', ')} />}
            {affsByType.collective && <ReadRow label="Members" value={affsByType.collective.join(', ')} secondary />}
            {affsByType.duo_partner && <ReadRow label="Duo" value={affsByType.duo_partner.join(', ')} secondary />}
            {Object.entries(affsByType).filter(([t]) => !['nation', 'collective', 'duo_partner'].includes(t)).map(([type, names]) => (
              <ReadRow key={type} label={capitalize(type.replace(/_/g, ' '))} value={names.join(', ')} secondary />
            ))}

            <div className="detail-tags">
              {(affsByType.nation ?? []).map(n => <span key={n} className="detail-tag identity-nation">{n}</span>)}
              {Object.entries(locsByType).flatMap(([type, places]) =>
                places.map(p => <span key={`${type}-${p}`} className={`detail-tag location-tag location-${type}`}>{p}</span>)
              )}
              {(tags.identities ?? []).map(l => <span key={l} className="detail-tag identity-tag-self">{l}</span>)}
            </div>
          </div>

          {/* Contact (editable) */}
          <div className="detail-section">
            <h3>Contact</h3>
            <EditRow label="Email" value={email} onChange={setEmail} type="email" placeholder="artist@example.com" missing={!email} />
            <EditRow label="Phone" value={phone} onChange={setPhone} placeholder="(604) 555-0100" missing={!phone} />
            <EditRow label="Website" value={website} onChange={setWebsite} type="url" placeholder="https://\u2026" missing={!website} />
            <div style={{ marginTop: '4px' }}>
              <span className="edit-label" style={{ display: 'block', marginBottom: '2px' }}>Notes</span>
              <textarea className="edit-input edit-textarea" value={contactNotes} onInput={e => setContactNotes((e.target as HTMLTextAreaElement).value)} placeholder="Any notes\u2026" />
            </div>
          </div>

          {/* Folders */}
          {fls.length > 0 && (
            <div className="detail-section">
              <h3>Folders ({fls.length})</h3>
              {fls.map((fl, i) => (
                <div key={i} className="folder-row">
                  <CategoryBadge category={fl.category} />
                  {fl.nation && <span className="identity-tag identity-nation">{fl.nation}</span>}
                  {fl.is_primary && <span className="folder-primary">(primary)</span>}
                  <span className="folder-path">{fl.folder_path}</span>
                  <button className="btn btn-sm btn-ghost" onClick={() => openFolderPath(fl.folder_path)} title="Open in Explorer" dangerouslySetInnerHTML={{ __html: ICO.folder }} />
                </div>
              ))}
            </div>
          )}

          {/* Documents */}
          <DocSection title="Bios" docs={docs.bios} openFile={openFile} bioText={bioText} />
          <DocSection title="CVs" docs={docs.cvs} openFile={openFile} />
          <DocSection title="Tearsheets" docs={docs.tearsheets} openFile={openFile} />
          <DocSection title="Project Lists" docs={docs.project_lists} openFile={openFile} />

          {/* EOIs */}
          {(eng.eois?.length ?? 0) > 0 && (
            <div className="detail-section">
              <h3>EOIs ({eng.eois.length})</h3>
              {eng.eois.map((e, i) => (
                <div key={i} className="engage-item">
                  <span className="doc-tag">EOI</span>
                  <span className="doc-link" onClick={() => openFile(e.file_path ?? '')}>
                    {e.project_name ?? basename(e.file_path) ?? 'Unknown'}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Concept Proposals */}
          {(eng.concept_proposals?.length ?? 0) > 0 && (
            <div className="detail-section">
              <h3>Concept Proposals ({eng.concept_proposals.length})</h3>
              {eng.concept_proposals.map((p, i) => {
                const parts = [p.project_name, p.developer].filter(Boolean)
                return (
                  <div key={i} className="engage-item">
                    <span className="doc-tag">{p.date ?? '?'}</span>
                    <span className="doc-link" onClick={() => openFile(p.file_path ?? '')}>
                      {parts.join(' \u2014 ') || basename(p.file_path) || 'Unknown'}
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Panel History */}
          <div className="detail-section">
            <h3>Panel History</h3>
            <div style={{ fontSize: '13px', marginBottom: '4px' }}><strong>{eng.panel_count ?? 0}</strong> appearances</div>
            {(eng.panel_history ?? []).map((p, i) => (
              <div key={i} className="engage-item">
                <span className="doc-tag">{p.date ?? '?'}</span>
                <span style={{ fontSize: '13px' }}>{p.project ?? ''}</span>
                {p.role && p.role !== 'selection_panel' && (
                  <span className="doc-tag">{p.role.replace(/_/g, ' ')}</span>
                )}
              </div>
            ))}
            {showPanelForm ? (
              <PanelForm artistId={m.artist_id} onDone={() => { setShowPanelForm(false); onRefresh() }} onCancel={() => setShowPanelForm(false)} />
            ) : (
              <button className="btn btn-sm" onClick={() => setShowPanelForm(true)}>+ Add Panel Entry</button>
            )}
          </div>

          {/* Public Art Projects */}
          <div className="detail-section">
            <h3>Public Art Projects</h3>
            {(eng.public_art_projects ?? []).map((p, i) => {
              const parts = [p.year, p.developer, p.project_name].filter(Boolean)
              return (
                <div key={i} className="engage-item">
                  <span style={{ fontSize: '13px' }}>{parts.join(' \u2014 ')}</span>
                  {p.status && <span className="doc-tag" style={{ color: statusColors[p.status] ?? 'var(--fg-secondary)' }}>{p.status}</span>}
                </div>
              )
            })}
            {showProjectForm ? (
              <ProjectForm artistId={m.artist_id} onDone={() => { setShowProjectForm(false); onRefresh() }} onCancel={() => setShowProjectForm(false)} />
            ) : (
              <button className="btn btn-sm" onClick={() => setShowProjectForm(true)}>+ Add Project</button>
            )}
          </div>

          {/* Images */}
          <div className="detail-section">
            <h3>Images</h3>
            <div style={{ fontSize: '13px' }}>{img.count ?? 0} image(s)</div>
            {(img.folder_paths ?? []).length > 0 && (
              <div className="doc-link" onClick={openFolder}>
                <span dangerouslySetInnerHTML={{ __html: ICO.folder }} /> Open image folder
              </div>
            )}
          </div>

          {/* Save bar */}
          <div className="save-bar">
            <button className="btn btn-primary" onClick={saveChanges} disabled={saving}>Save Changes</button>
            <FeedbackMessage message={saveFeedback} isError={saveErr} />
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
            <span style={{ flex: 1 }} />
            <button className="btn btn-sm" onClick={openFolder}>
              <span dangerouslySetInnerHTML={{ __html: ICO.folder }} /> Open Folder
            </button>
            <button className="btn btn-sm" onClick={rescan}>Rescan</button>
          </div>
        </div>
      </aside>
    </>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function EditRow({ label, value, onChange, type, placeholder, missing }: {
  label: string; value: string; onChange: (v: string) => void
  type?: string; placeholder?: string; missing?: boolean
}) {
  return (
    <div className="edit-row">
      <span className="edit-label">{label}</span>
      <input
        className={`edit-input${missing ? ' missing-highlight' : ''}`}
        type={type ?? 'text'}
        value={value}
        onInput={e => onChange((e.target as HTMLInputElement).value)}
        placeholder={placeholder}
      />
    </div>
  )
}

function ReadRow({ label, value, secondary }: { label: string; value: string; secondary?: boolean }) {
  return (
    <div className="edit-row">
      <span className="edit-label">{label}</span>
      <span style={{ fontSize: '13px', color: secondary ? 'var(--fg-secondary)' : undefined }}>{value}</span>
    </div>
  )
}

function DocSection({ title, docs, openFile, bioText }: {
  title: string; docs: DocumentEntry[]; openFile: (p: string) => void; bioText?: string
}) {
  if (!docs?.length) return null
  return (
    <div className="detail-section">
      <h3>{title} ({docs.length})</h3>
      {docs.map((d, i) => {
        const name = basename(d.file_path) || 'Unknown'
        return (
          <div key={i} className={`doc-link${d.is_current ? ' current' : ''}`} onClick={() => openFile(d.file_path ?? '')} title={d.file_path ?? ''}>
            <span className={`doc-tag${d.is_current ? ' current' : ' old'}`}>{d.is_current ? 'current' : 'old'}</span>
            {' '}{name}{d.date ? ` (${d.date})` : ''}
          </div>
        )
      })}
      {title === 'Bios' && bioText && <div className="bio-content">{bioText}</div>}
    </div>
  )
}

function PanelForm({ artistId, onDone, onCancel }: { artistId: string; onDone: () => void; onCancel: () => void }) {
  const dateRef = useRef<HTMLInputElement>(null)
  const projectRef = useRef<HTMLInputElement>(null)
  const roleRef = useRef<HTMLSelectElement>(null)

  const submit = async () => {
    await api.artists.addPanel(artistId, {
      date: dateRef.current?.value ?? '',
      project: projectRef.current?.value ?? '',
      role: roleRef.current?.value ?? 'selection_panel',
    })
    onDone()
  }

  return (
    <div className="inline-form">
      <input ref={dateRef} type="date" />
      <input ref={projectRef} type="text" placeholder="Project name" style={{ flex: 1 }} />
      <select ref={roleRef} style={{ padding: '4px 6px', fontSize: '13px', border: '1px solid var(--border)', borderRadius: '2px' }}>
        <option value="selection_panel">Selection Panel</option>
        <option value="community_advisor">Community Advisor</option>
        <option value="cultural_advisor">Cultural Advisor</option>
        <option value="juror">Juror</option>
      </select>
      <button className="btn btn-sm btn-primary" onClick={submit}>Add</button>
      <button className="btn btn-sm" onClick={onCancel}>Cancel</button>
    </div>
  )
}

function ProjectForm({ artistId, onDone, onCancel }: { artistId: string; onDone: () => void; onCancel: () => void }) {
  const nameRef = useRef<HTMLInputElement>(null)
  const devRef = useRef<HTMLInputElement>(null)
  const yearRef = useRef<HTMLInputElement>(null)
  const roleRef = useRef<HTMLInputElement>(null)
  const statusRef = useRef<HTMLSelectElement>(null)

  const submit = async () => {
    const name = nameRef.current?.value?.trim()
    if (!name) return
    await api.artists.addProject(artistId, {
      project_name: name,
      developer: devRef.current?.value?.trim() || null,
      year: yearRef.current?.value?.trim() || null,
      role: roleRef.current?.value?.trim() || null,
      status: statusRef.current?.value ?? 'submitted',
    })
    onDone()
  }

  return (
    <div className="inline-form" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
      <div style={{ display: 'flex', gap: '6px' }}>
        <input ref={nameRef} type="text" placeholder="Project name*" style={{ flex: 1 }} />
        <input ref={devRef} type="text" placeholder="Developer" style={{ flex: 1 }} />
      </div>
      <div style={{ display: 'flex', gap: '6px' }}>
        <input ref={yearRef} type="text" placeholder="Year" style={{ width: '70px' }} />
        <input ref={roleRef} type="text" placeholder="Role" style={{ flex: 1 }} />
        <select ref={statusRef} style={{ flex: 1, padding: '4px 6px', fontSize: '13px', border: '1px solid var(--border)', borderRadius: '2px' }}>
          <option value="submitted">Submitted</option>
          <option value="longlisted">Longlisted</option>
          <option value="shortlisted">Shortlisted</option>
          <option value="awarded">Awarded</option>
          <option value="completed">Completed</option>
        </select>
      </div>
      <div style={{ display: 'flex', gap: '6px' }}>
        <button className="btn btn-sm btn-primary" onClick={submit}>Add</button>
        <button className="btn btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
