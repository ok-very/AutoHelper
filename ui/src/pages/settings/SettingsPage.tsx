import { useState, useEffect, useRef, useCallback } from 'react'
import { ModuleLayout } from '@/components/ModuleLayout'
import { FeedbackMessage } from '@/components/FeedbackMessage'
import { api } from '@/lib/api'
import type { AppConfig, Lexicon, ScanStatus } from '@/lib/types'

const LEXICON_TABS = [
  { key: 'categories', label: 'Categories' },
  { key: 'subfolder_aliases', label: 'Aliases' },
  { key: 'completeness_weights', label: 'Weights' },
  { key: 'identity_options', label: 'Identities' },
  { key: 'affiliation_types', label: 'Affiliation Types' },
  { key: 'location_types', label: 'Location Types' },
  { key: 'name_types', label: 'Name Types' },
  { key: 'career_stages', label: 'Career Stages' },
  { key: 'folder_name_fixes', label: 'Fixes' },
  { key: 'multi_folder_artists', label: 'Multi-Folder' },
  { key: 'full', label: 'Full JSON' },
] as const

type LexiconTab = typeof LEXICON_TABS[number]['key']

export function SettingsPage() {
  return (
    <ModuleLayout module="artist-directory" activePage="settings">
      <header className="header">
        <h1>Artist Settings</h1>
      </header>
      <div className="settings-grid">
        <ConfigCard />
        <ScanCard />
      </div>
      <LexiconCard />
    </ModuleLayout>
  )
}

// ---------------------------------------------------------------------------
// Config Card
// ---------------------------------------------------------------------------

function ConfigCard() {
  const [storageRoot, setStorageRoot] = useState('')
  const [groundTruth, setGroundTruth] = useState('')
  const [scanEnabled, setScanEnabled] = useState(false)
  const [scanOnChange, setScanOnChange] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.config.get().then(cfg => {
      setStorageRoot(cfg.artist_storage_root ?? '')
      setGroundTruth(cfg.artist_ground_truth_csv ?? '')
      setScanEnabled(!!cfg.artist_scan_enabled)
      setScanOnChange(!!cfg.artist_scan_on_change)
    }).catch(() => {
      setFeedback('\u2717 Could not load config')
      setFeedbackErr(true)
    })
  }, [])

  const browse = async (setter: (v: string) => void) => {
    let path: string | null = null
    if (window.electronAPI?.selectFolder) {
      path = await window.electronAPI.selectFolder()
    } else {
      const d = await api.config.selectFolder()
      path = d.path
    }
    if (path) setter(path)
  }

  const save = async () => {
    setSaving(true)
    setFeedback('Saving\u2026')
    setFeedbackErr(false)
    try {
      const r = await api.config.save({
        artist_storage_root: storageRoot.trim(),
        artist_ground_truth_csv: groundTruth.trim(),
        artist_scan_enabled: scanEnabled,
        artist_scan_on_change: scanOnChange,
      })
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
      <h3>Storage &amp; Scanning</h3>
      <div className="setting-row">
        <span className="setting-label">Storage Root</span>
        <div style={{ display: 'flex', gap: '6px', flex: 1 }}>
          <input type="text" className="setting-input" value={storageRoot} onInput={e => setStorageRoot((e.target as HTMLInputElement).value)} placeholder="/path/to/artist/files" style={{ flex: 1 }} />
          <button className="btn" onClick={() => browse(setStorageRoot)}>Browse</button>
        </div>
      </div>
      <div className="setting-row">
        <span className="setting-label">Ground Truth CSV</span>
        <div style={{ display: 'flex', gap: '6px', flex: 1 }}>
          <input type="text" className="setting-input" value={groundTruth} onInput={e => setGroundTruth((e.target as HTMLInputElement).value)} placeholder="/path/to/final_7450_full.csv" style={{ flex: 1 }} />
          <button className="btn" onClick={() => browse(setGroundTruth)}>Browse</button>
        </div>
      </div>
      <div className="setting-row">
        <span className="setting-label">Enable Scanning</span>
        <label className="toggle">
          <input type="checkbox" checked={scanEnabled} onChange={e => setScanEnabled((e.target as HTMLInputElement).checked)} />
          <span className="toggle-slider" />
        </label>
      </div>
      <div className="setting-row">
        <span className="setting-label">Auto-Rescan on Change</span>
        <label className="toggle">
          <input type="checkbox" checked={scanOnChange} onChange={e => setScanOnChange((e.target as HTMLInputElement).checked)} />
          <span className="toggle-slider" />
        </label>
      </div>
      <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>Save Config</button>
        <FeedbackMessage message={feedback} isError={feedbackErr} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Scan Card
// ---------------------------------------------------------------------------

function ScanCard() {
  const [scanning, setScanning] = useState(false)
  const [status, setStatus] = useState('')
  const [info, setInfo] = useState('')
  const [lines, setLines] = useState<string[]>([])
  const [showTerminal, setShowTerminal] = useState(false)
  const terminalRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  const connectLog = useCallback(() => {
    esRef.current?.close()
    const es = new EventSource(api.scan.logUrl)
    esRef.current = es

    es.onmessage = (e) => {
      if (e.data === '[done]') {
        es.close()
        esRef.current = null
        onFinished()
        return
      }
      setLines(prev => [...prev, e.data])
    }

    es.onerror = () => {
      es.close()
      esRef.current = null
      onFinished()
    }
  }, [])

  const onFinished = async () => {
    setScanning(false)
    try {
      const d = await api.scan.status()
      if (d.last_run) {
        const s = d.last_run.stats
        const st = d.last_run.status
        setStatus(st === 'completed' ? `Done: ${s?.artists ?? 0} artists` : st.charAt(0).toUpperCase() + st.slice(1))
        setInfo(d.last_run.finished_at ? `Finished: ${d.last_run.finished_at}` : '')
      } else {
        setStatus('No scans yet')
      }
    } catch {
      setStatus('Unable to load status')
    }
  }

  const triggerScan = async () => {
    setScanning(true)
    setStatus('Starting\u2026')
    setLines([])
    setShowTerminal(true)
    try {
      const r = await api.scan.trigger()
      if (!r.ok) {
        const d = await r.json().catch(() => ({} as Record<string, string>))
        setStatus(d.detail ?? 'Error')
        setScanning(false)
        return
      }
    } catch {
      setStatus('Network error')
      setScanning(false)
      return
    }
    setStatus('Scanning\u2026')
    connectLog()
  }

  const stopScan = async () => {
    setStatus('Stopping\u2026')
    try { await api.scan.stop() } catch { /* ignore */ }
  }

  // Check for active scan on mount
  useEffect(() => {
    api.scan.status().then(d => {
      if (d.is_scanning) {
        setScanning(true)
        setStatus('Scanning\u2026')
        setShowTerminal(true)
        connectLog()
      } else if (d.last_run) {
        const s = d.last_run.stats
        const st = d.last_run.status
        setStatus(st === 'completed' ? `Last: ${s?.artists ?? 0} artists` : `Last: ${st}`)
        setInfo(d.last_run.finished_at ? `Finished: ${d.last_run.finished_at}` : '')
      }
    }).catch(() => {})

    return () => { esRef.current?.close() }
  }, [connectLog])

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [lines])

  return (
    <div className="settings-card">
      <h3>Scan Controls</h3>
      <div style={{ marginBottom: '8px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={triggerScan} disabled={scanning}>Scan All</button>
        <button className="btn btn-warning" onClick={stopScan} disabled={!scanning}>Stop</button>
        <span className="scan-status" style={{ marginLeft: '4px' }}>{status}</span>
      </div>
      {info && <div style={{ fontSize: '12px', color: 'var(--fg-secondary)', marginBottom: '8px' }}>{info}</div>}
      {showTerminal && (
        <div ref={terminalRef} className="scan-terminal" style={{ display: 'block' }}>
          {lines.map((line, i) => (
            <div key={i} className="scan-line">{line}</div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Lexicon Card
// ---------------------------------------------------------------------------

function LexiconCard() {
  const [fullLexicon, setFullLexicon] = useState<Lexicon>({})
  const [currentSection, setCurrentSection] = useState<LexiconTab>('categories')
  const [editorValue, setEditorValue] = useState('')
  const [invalid, setInvalid] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)
  const [saving, setSaving] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.lexicon.get().then(data => {
      setFullLexicon(data)
      renderSection(data, 'categories')
    }).catch(() => {
      setFeedback('\u2717 Failed to load lexicon')
      setFeedbackErr(true)
    })
  }, [])

  function renderSection(lex: Lexicon, section: LexiconTab) {
    if (section === 'full') {
      setEditorValue(JSON.stringify(lex, null, 2))
    } else {
      const s = lex[section]
      setEditorValue(s !== undefined ? JSON.stringify(s, null, 2) : '{}')
    }
    setInvalid(false)
  }

  function saveEditsToMemory(): Lexicon {
    try {
      const parsed = JSON.parse(editorValue)
      const updated = currentSection === 'full' ? parsed : { ...fullLexicon, [currentSection]: parsed }
      setFullLexicon(updated)
      setInvalid(false)
      return updated
    } catch {
      setInvalid(true)
      return fullLexicon
    }
  }

  const switchTab = (tab: LexiconTab) => {
    const updated = saveEditsToMemory()
    setCurrentSection(tab)
    renderSection(updated, tab)
  }

  const save = async () => {
    const data = saveEditsToMemory()
    setSaving(true)
    setFeedback('Saving\u2026')
    setFeedbackErr(false)
    try {
      const r = await api.lexicon.save(data)
      if (r.ok) { setFeedback('\u2713 Saved'); setFeedbackErr(false) }
      else {
        const d = await r.json().catch(() => ({} as Record<string, string>))
        setFeedback('\u2717 ' + (d.detail ?? 'Error'))
        setFeedbackErr(true)
      }
    } catch {
      setFeedback('\u2717 Network error')
      setFeedbackErr(true)
    }
    setSaving(false)
  }

  const reset = async () => {
    if (!confirm('Reset lexicon to defaults? Current edits will be lost.')) return
    try {
      const data = await api.lexicon.get()
      setFullLexicon(data)
      renderSection(data, currentSection)
      setFeedback('Reloaded from disk')
      setFeedbackErr(false)
    } catch {
      setFeedback('\u2717 Error')
      setFeedbackErr(true)
    }
  }

  const exportLexicon = () => {
    const data = saveEditsToMemory()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'artist_lexicon.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const importLexicon = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = JSON.parse(reader.result as string)
        setFullLexicon(parsed)
        renderSection(parsed, currentSection)
        setFeedback('Imported \u2014 click Save to persist')
        setFeedbackErr(false)
      } catch {
        setFeedback('\u2717 Invalid JSON file')
        setFeedbackErr(true)
      }
    }
    reader.readAsText(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="settings-card full-width" style={{ marginBottom: '16px' }}>
      <h3>Lexicon Configuration</h3>
      <p style={{ fontSize: '12px', color: 'var(--fg-secondary)', marginBottom: '12px' }}>
        Edit the artist lexicon (category profiles, subfolder aliases, completeness weights, identity options, affiliation types, folder name fixes, multi-folder overrides).
      </p>

      <div style={{ display: 'flex', gap: 0, marginBottom: '12px', borderBottom: '1px solid var(--border)' }}>
        {LEXICON_TABS.map(t => (
          <button
            key={t.key}
            className={`btn btn-ghost lexicon-tab${t.key === currentSection ? ' active' : ''}`}
            onClick={() => switchTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div>
        <textarea
          className={`json-editor${invalid ? ' invalid' : ''}`}
          rows={16}
          value={editorValue}
          onInput={e => setEditorValue((e.target as HTMLTextAreaElement).value)}
        />
      </div>

      <div style={{ marginTop: '10px', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>Save Lexicon</button>
        <button className="btn" onClick={reset}>Reset to Defaults</button>
        <button className="btn" onClick={exportLexicon}>Export</button>
        <label className="btn" style={{ margin: 0 }}>
          Import <input ref={fileInputRef} type="file" accept=".json" style={{ display: 'none' }} onChange={importLexicon} />
        </label>
        <FeedbackMessage message={feedback} isError={feedbackErr} />
      </div>
    </div>
  )
}
