import { useState, useEffect, useCallback } from 'react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'

export function SubmissionsSettingsPage() {
  return (
    <ModuleLayout module="image-sorting" activePage="settings">
      <header className="header">
        <h1>Submissions Settings</h1>
      </header>
      <div className="settings-grid">
        <ImageFoldersCard />
        <ExportPathCard />
        <ManifestCard />
      </div>
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Image Folders Card — add/remove watch folders for image serving
// ---------------------------------------------------------------------------

function ImageFoldersCard() {
  const [roots, setRoots] = useState<string[]>([])
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.config.get().then(cfg => {
      setRoots((cfg.image_allowed_roots as string[] | undefined) ?? [])
    }).catch(() => {
      setFeedback('\u2717 Could not load config')
      setFeedbackErr(true)
    })
  }, [])

  const save = useCallback(async (next: string[]) => {
    setSaving(true)
    setFeedback('Saving\u2026')
    setFeedbackErr(false)
    try {
      const r = await api.config.save({ image_allowed_roots: next })
      if (r.ok) {
        setRoots(next)
        setFeedback('\u2713 Saved')
        setFeedbackErr(false)
      } else {
        setFeedback('\u2717 Error')
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('\u2717 Network error')
      setFeedbackErr(true)
    }
    setSaving(false)
  }, [])

  const addFolder = async () => {
    const d = await api.config.selectFolder()
    if (d.path && !roots.includes(d.path)) {
      await save([...roots, d.path])
    }
  }

  const addManual = () => {
    const path = prompt('Enter folder path:')
    if (path && path.trim() && !roots.includes(path.trim())) {
      save([...roots, path.trim()])
    }
  }

  const remove = (idx: number) => {
    save(roots.filter((_, i) => i !== idx))
  }

  return (
    <div className="settings-card">
      <h3>Image Folders</h3>
      <p style={{ fontSize: '12px', color: 'var(--fg-secondary)', marginBottom: '12px' }}>
        Directories the image proxy is allowed to serve. Add the base directories that contain your submission images.
      </p>

      {roots.length === 0 ? (
        <p style={{ fontSize: '13px', color: 'var(--color-warning)', marginBottom: '10px' }}>
          No folders configured — images won't load in the review panel.
        </p>
      ) : (
        <div style={{ marginBottom: '10px' }}>
          {roots.map((root, i) => (
            <div key={i} className="setting-row" style={{ marginBottom: '4px' }}>
              <span style={{
                flex: 1,
                fontFamily: 'var(--font-mono)',
                fontSize: '12px',
                color: 'var(--fg)',
                wordBreak: 'break-all',
              }}>
                {root}
              </span>
              <button className="btn btn-sm btn-danger" onClick={() => remove(i)}>&times;</button>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button className="btn" onClick={addFolder}>+ Browse</button>
        <button className="btn" onClick={addManual}>+ Type Path</button>
        <FeedbackMessage message={feedback} isError={feedbackErr} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Export Path Card — configurable export output directory
// ---------------------------------------------------------------------------

function ExportPathCard() {
  const [exportDir, setExportDir] = useState('')
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.config.get().then(cfg => {
      setExportDir((cfg.export_output_dir as string) ?? '')
    }).catch(() => {
      setFeedback('\u2717 Could not load config')
      setFeedbackErr(true)
    })
  }, [])

  const browse = async () => {
    let path: string | null = null
    if ((window as any).electronAPI?.selectFolder) {
      path = await (window as any).electronAPI.selectFolder()
    } else {
      const d = await api.config.selectFolder()
      path = d.path
    }
    if (path) setExportDir(path)
  }

  const save = async () => {
    setSaving(true)
    setFeedback('Saving\u2026')
    setFeedbackErr(false)
    try {
      const r = await api.config.save({ export_output_dir: exportDir.trim() })
      if (r.ok) { setFeedback('\u2713 Saved'); setFeedbackErr(false) }
      else { setFeedback('\u2717 Error'); setFeedbackErr(true) }
    } catch {
      setFeedback('\u2717 Network error')
      setFeedbackErr(true)
    }
    setSaving(false)
  }

  return (
    <div className="settings-card">
      <h3>Export Output</h3>
      <p style={{ fontSize: '12px', color: 'var(--fg-secondary)', marginBottom: '12px' }}>
        Directory for CSV exports. Leave empty to use the default (data_dir/exports/).
      </p>
      <div className="setting-row">
        <div style={{ display: 'flex', gap: '6px', flex: 1 }}>
          <input
            type="text"
            className="setting-input"
            value={exportDir}
            onInput={e => setExportDir((e.target as HTMLInputElement).value)}
            placeholder="C:\path\to\exports"
            style={{ flex: 1 }}
          />
          <button className="btn" onClick={browse}>Browse</button>
        </div>
      </div>
      <div style={{ marginTop: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>Save</button>
        <FeedbackMessage message={feedback} isError={feedbackErr} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Manifest Card — manifest upload / link
// ---------------------------------------------------------------------------

interface ManifestInfo {
  id: string
  name: string
  slug: string
  imageBases: string[]
}

function ManifestCard() {
  const [manifests, setManifests] = useState<ManifestInfo[]>([])
  const [configuredRoots, setConfiguredRoots] = useState<string[]>([])
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)

  useEffect(() => {
    // Load config roots
    api.config.get().then(cfg => {
      setConfiguredRoots((cfg.image_allowed_roots as string[] | undefined) ?? [])
    }).catch(() => {})

    // Load manifest
    const slug = 'burnaby-hospital'
    fetch(`/manifests/${slug}.json`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.id) {
          setManifests([{
            id: data.id,
            name: data.name ?? data.id,
            slug,
            imageBases: data.dataSources?.imageBases ?? [],
          }])
        }
      })
      .catch(() => {})
  }, [])

  const addBase = async (path: string) => {
    const next = [...configuredRoots, path]
    try {
      const r = await api.config.save({ image_allowed_roots: next })
      if (r.ok) {
        setConfiguredRoots(next)
        setFeedback(`\u2713 Added`)
        setFeedbackErr(false)
      }
    } catch {
      setFeedback('\u2717 Failed to save')
      setFeedbackErr(true)
    }
  }

  const normalizePath = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()

  return (
    <div className="settings-card">
      <h3>Manifests</h3>
      <p style={{ fontSize: '12px', color: 'var(--fg-secondary)', marginBottom: '12px' }}>
        Available submission manifests. Add their image folders to enable image loading.
      </p>

      {manifests.length === 0 ? (
        <p style={{ fontSize: '13px', color: 'var(--fg-secondary)' }}>No manifests found.</p>
      ) : (
        manifests.map(m => (
          <div key={m.id} style={{ marginBottom: '16px' }}>
            <div className="setting-row" style={{ marginBottom: '8px' }}>
              <strong style={{ fontSize: '14px' }}>{m.name}</strong>
              <a
                href={`/image-sorting?manifest=${m.slug}`}
                className="btn btn-sm"
                style={{ marginLeft: 'auto' }}
              >
                Open Review
              </a>
            </div>

            {m.imageBases.length > 0 && (
              <div style={{ marginLeft: '8px' }}>
                <span style={{ fontSize: '11px', color: 'var(--fg-secondary)', fontWeight: 600 }}>
                  Image folders from manifest:
                </span>
                {m.imageBases.map((base, i) => {
                  const isAdded = configuredRoots.some(r => normalizePath(r) === normalizePath(base))
                  return (
                    <div key={i} className="setting-row" style={{ marginTop: '4px', gap: '8px' }}>
                      <span style={{
                        flex: 1,
                        fontFamily: 'var(--font-mono)',
                        fontSize: '11px',
                        color: isAdded ? 'var(--fg)' : 'var(--color-warning)',
                        wordBreak: 'break-all',
                      }}>
                        {base}
                      </span>
                      {isAdded ? (
                        <span style={{ fontSize: '11px', color: 'var(--color-success)' }}>{'\u2713'} added</span>
                      ) : (
                        <button className="btn btn-sm" onClick={() => addBase(base)}>+ Add</button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            <FeedbackMessage message={feedback} isError={feedbackErr} />
          </div>
        ))
      )}
    </div>
  )
}
