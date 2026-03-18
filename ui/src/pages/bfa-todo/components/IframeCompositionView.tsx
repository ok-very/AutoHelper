import { useState, useEffect, useCallback, useRef } from 'react'
import { Save, X } from 'lucide-react'

interface IframeCompositionViewProps {
  uid: string
  fetchUrl: string
  onSaveSection: (sectionName: string, html: string) => Promise<any>
  title?: string
}

export function IframeCompositionView({
  uid, fetchUrl, onSaveSection, title,
}: IframeCompositionViewProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(80)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [srcdoc, setSrcdoc] = useState<string | null>(null)
  const [editingSection, setEditingSection] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const originalHtmlRef = useRef<string>('')

  const fetchHtml = useCallback(() => {
    setLoading(true)
    setError(false)
    fetch(fetchUrl)
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`)
        return r.text()
      })
      .then(html => {
        setSrcdoc(html)
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }, [fetchUrl])

  useEffect(() => { fetchHtml() }, [fetchHtml])

  const resizeIframe = useCallback(() => {
    const iframe = iframeRef.current
    if (!iframe) return
    try {
      const doc = iframe.contentDocument
      if (doc?.body) {
        requestAnimationFrame(() => {
          const h = doc.body.scrollHeight
          if (h > 0) setHeight(h + 8)
        })
      }
    } catch { /* cross-origin */ }
  }, [])

  const onLoad = useCallback(() => {
    resizeIframe()
    const doc = iframeRef.current?.contentDocument
    if (!doc) return
    const style = doc.createElement('style')
    style.textContent = `
      [data-section] { position: relative; transition: outline 0.12s; }
      [data-section]:hover { outline: 1px dashed rgba(63, 92, 110, 0.3); outline-offset: 2px; cursor: pointer; }
      [data-section].editing { outline: 2px solid #3F5C6E; outline-offset: 2px; cursor: text; }
      [data-section].editing:focus { outline: 2px solid #3F5C6E; }
    `
    doc.head.appendChild(style)

    doc.body.addEventListener('click', (e: Event) => {
      const target = (e.target as HTMLElement).closest('[data-section]') as HTMLElement | null
      if (!target) return
      const secName = target.dataset.section
      if (secName) {
        window.postMessage({ type: 'bfa-edit-section', uid, section: secName }, '*')
      }
    })
  }, [uid, resizeIframe])

  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'bfa-edit-section' && e.data.uid === uid) {
        const secName = e.data.section
        if (editingSection === secName) return
        startEditInIframe(secName)
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  })

  const startEditInIframe = useCallback((secName: string) => {
    const doc = iframeRef.current?.contentDocument
    if (!doc) return
    if (editingSection) {
      const prev = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
      if (prev) {
        prev.contentEditable = 'false'
        prev.classList.remove('editing')
        prev.innerHTML = originalHtmlRef.current
      }
    }
    const el = doc.querySelector(`[data-section="${secName}"]`) as HTMLElement | null
    if (!el) return
    originalHtmlRef.current = el.innerHTML
    el.contentEditable = 'true'
    el.classList.add('editing')
    el.style.outline = 'none'
    el.focus()
    setEditingSection(secName)
    requestAnimationFrame(resizeIframe)
  }, [editingSection, resizeIframe])

  const cancelEdit = useCallback(() => {
    const doc = iframeRef.current?.contentDocument
    if (!doc || !editingSection) return
    const el = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
    if (el) {
      el.contentEditable = 'false'
      el.classList.remove('editing')
      el.innerHTML = originalHtmlRef.current
    }
    setEditingSection(null)
  }, [editingSection])

  const saveEdit = useCallback(async () => {
    const doc = iframeRef.current?.contentDocument
    if (!doc || !editingSection) return
    const el = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
    if (!el) return

    setSaving(true)
    try {
      await onSaveSection(editingSection, el.innerHTML)
      el.contentEditable = 'false'
      el.classList.remove('editing')
      setEditingSection(null)
      fetchHtml()
    } catch {
      // stay in edit mode
    } finally {
      setSaving(false)
    }
  }, [editingSection, onSaveSection, fetchHtml])

  if (loading) {
    return (
      <div style={{ padding: '4px 40px 12px', fontSize: '12px', color: 'var(--fg-secondary)', fontFamily: 'var(--font-sans)' }}>
        Loading...
      </div>
    )
  }

  if (error || !srcdoc) {
    return (
      <div style={{ padding: '4px 40px 12px', fontSize: '12px', color: 'var(--color-error)', fontFamily: 'var(--font-sans)' }}>
        Failed to load HTML
      </div>
    )
  }

  return (
    <div style={{ padding: '2px 12px 8px 40px' }}>
      {editingSection && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, fontFamily: 'var(--font-sans)' }}>
          <span style={{ fontSize: '11px', color: 'var(--fg-secondary)' }}>
            Editing section — click to edit text, then:
          </span>
          <button
            className="btn btn-sm btn-primary"
            onClick={saveEdit}
            disabled={saving}
            style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}
          >
            <Save size={11} /> {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            className="btn btn-sm"
            onClick={cancelEdit}
            disabled={saving}
            style={{ fontSize: '11px', padding: '2px 8px', gap: 3, display: 'flex', alignItems: 'center' }}
          >
            <X size={11} /> Cancel
          </button>
        </div>
      )}
      <iframe
        ref={iframeRef}
        srcDoc={srcdoc}
        onLoad={onLoad}
        style={{
          width: '100%',
          height: `${height}px`,
          border: 'none',
          display: 'block',
          background: '#fff',
        }}
        title={title || uid}
      />
    </div>
  )
}
