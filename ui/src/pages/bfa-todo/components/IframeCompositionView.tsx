import { useState, useEffect, useCallback, useRef } from 'react'
import { Save, X } from 'lucide-react'

interface IframeCompositionViewProps {
  uid: string
  fetchUrl: string
  onSaveSection: (sectionName: string, html: string) => Promise<any>
  title?: string
}

/**
 * CSS + JS injected into the iframe document to provide:
 * - Section hover/edit outlines
 * - Floating formatting toolbar (bold, italic, strike, highlight, font size)
 * - All execCommand calls run inside the iframe's isolated context
 */
const IFRAME_EDITOR_STYLES = `
  [data-section] { position: relative; transition: outline 0.12s; }
  [data-section]:hover { outline: 1px dashed rgba(63, 92, 110, 0.3); outline-offset: 2px; cursor: pointer; }
  [data-section].editing { outline: 2px solid #3F5C6E; outline-offset: 2px; cursor: text; }
  [data-section].editing:hover { outline: 2px solid #3F5C6E; }

  .bfa-toolbar {
    position: absolute;
    left: 0;
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 3px 6px;
    background: #fff;
    border: 1px solid #D6D2CB;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    z-index: 9999;
    font-family: "Source Sans 3", "Segoe UI", sans-serif;
    font-size: 11px;
    user-select: none;
  }
  .bfa-toolbar button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 24px;
    border: none;
    border-radius: 3px;
    background: transparent;
    color: #5A5A57;
    cursor: pointer;
    font-size: 12px;
    font-family: inherit;
    padding: 0;
    line-height: 1;
  }
  .bfa-toolbar button:hover { background: rgba(63, 92, 110, 0.08); }
  .bfa-toolbar button.active { background: rgba(63, 92, 110, 0.12); color: #2E2E2C; }
  .bfa-toolbar .sep {
    width: 1px;
    height: 16px;
    background: #D6D2CB;
    margin: 0 2px;
    flex-shrink: 0;
  }
  .bfa-toolbar select {
    height: 22px;
    border: 1px solid #D6D2CB;
    border-radius: 3px;
    background: transparent;
    color: #5A5A57;
    font-size: 10px;
    font-family: inherit;
    cursor: pointer;
    padding: 0 2px;
    outline: none;
  }
  .bfa-toolbar .hl-swatch {
    width: 16px;
    height: 16px;
    border-radius: 2px;
    border: 1px solid #D6D2CB;
    cursor: pointer;
    padding: 0;
    display: inline-block;
  }
  .bfa-toolbar .hl-swatch.active { border: 2px solid #3F5C6E; }
  .bfa-toolbar .hl-group {
    display: none;
    align-items: center;
    gap: 3px;
    padding: 3px;
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 2px;
    background: #fff;
    border: 1px solid #D6D2CB;
    border-radius: 4px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  }
  .bfa-toolbar .hl-group.open { display: flex; }
`

/**
 * Script injected into the iframe. Creates the toolbar DOM and wires
 * execCommand calls + selection state tracking. Communicates with
 * the parent via postMessage.
 */
const IFRAME_EDITOR_SCRIPT = `
(function() {
  var toolbar = null;
  var activeSection = null;
  var hlOpen = false;

  var HIGHLIGHT_COLORS = [
    { label: 'Yellow', hex: '#FFF3B0' },
    { label: 'Green', hex: '#D4EDBC' },
    { label: 'Cyan', hex: '#B5E8EC' },
  ];

  function createToolbar() {
    if (toolbar) return toolbar;
    toolbar = document.createElement('div');
    toolbar.className = 'bfa-toolbar';
    toolbar.innerHTML =
      '<button data-cmd="bold" title="Bold"><b>B</b></button>' +
      '<button data-cmd="italic" title="Italic"><i>I</i></button>' +
      '<button data-cmd="strikeThrough" title="Strikethrough"><s>S</s></button>' +
      '<span class="sep"></span>' +
      '<button data-cmd="highlight" title="Highlight">H</button>' +
      '<div class="hl-group" id="bfa-hl-group"></div>' +
      '<span class="sep"></span>' +
      '<select data-cmd="fontSize" title="Font size">' +
      '  <option value="">Size</option>' +
      '  <option value="1">8pt</option>' +
      '  <option value="3">11pt</option>' +
      '</select>' +
      '<span class="sep"></span>' +
      '<button data-cmd="insertUnorderedList" title="Bullet list">&#8226;</button>';

    // Build highlight swatches
    var hlGroup = toolbar.querySelector('#bfa-hl-group');
    HIGHLIGHT_COLORS.forEach(function(c) {
      var btn = document.createElement('button');
      btn.className = 'hl-swatch';
      btn.style.background = c.hex;
      btn.title = c.label;
      btn.setAttribute('data-hl-color', c.hex);
      btn.addEventListener('mousedown', function(e) {
        e.preventDefault();
        applyHighlight(c.hex);
        closeHlGroup();
      });
      hlGroup.appendChild(btn);
    });
    // Remove highlight button
    var rmBtn = document.createElement('button');
    rmBtn.className = 'hl-swatch';
    rmBtn.style.background = '#fff';
    rmBtn.title = 'Remove';
    rmBtn.textContent = '×';
    rmBtn.style.fontSize = '12px';
    rmBtn.style.lineHeight = '14px';
    rmBtn.addEventListener('mousedown', function(e) {
      e.preventDefault();
      removeHighlight();
      closeHlGroup();
    });
    hlGroup.appendChild(rmBtn);

    // Wire toolbar buttons
    toolbar.addEventListener('mousedown', function(e) {
      e.preventDefault(); // keep focus in contentEditable
      var btn = e.target.closest('button[data-cmd]');
      if (!btn) return;
      var cmd = btn.getAttribute('data-cmd');
      if (cmd === 'highlight') {
        hlOpen = !hlOpen;
        hlGroup.classList.toggle('open', hlOpen);
        return;
      }
      document.execCommand(cmd, false, null);
      updateToolbarState();
    });

    // Wire font size select
    var sizeSelect = toolbar.querySelector('select[data-cmd="fontSize"]');
    sizeSelect.addEventListener('change', function(e) {
      e.preventDefault();
      var val = e.target.value;
      if (val) {
        document.execCommand('fontSize', false, val);
        // execCommand fontSize uses <font size="N"> — convert to inline style
        var fonts = activeSection ? activeSection.querySelectorAll('font[size]') : [];
        for (var i = 0; i < fonts.length; i++) {
          var f = fonts[i];
          var span = document.createElement('span');
          span.style.fontSize = f.getAttribute('size') === '1' ? '8pt' : '11pt';
          span.innerHTML = f.innerHTML;
          f.parentNode.replaceChild(span, f);
        }
      }
      updateToolbarState();
      sizeSelect.value = '';
    });

    document.body.appendChild(toolbar);
    return toolbar;
  }

  function applyHighlight(color) {
    // Use hiliteColor (non-IE) or backColor
    document.execCommand('hiliteColor', false, color);
    updateToolbarState();
  }

  function removeHighlight() {
    document.execCommand('hiliteColor', false, 'transparent');
    updateToolbarState();
  }

  function closeHlGroup() {
    hlOpen = false;
    var g = document.getElementById('bfa-hl-group');
    if (g) g.classList.remove('open');
  }

  function positionToolbar(sectionEl) {
    if (!toolbar) return;
    var rect = sectionEl.getBoundingClientRect();
    toolbar.style.top = (rect.top + window.scrollY - toolbar.offsetHeight - 6) + 'px';
    toolbar.style.left = rect.left + 'px';
  }

  function updateToolbarState() {
    if (!toolbar) return;
    var cmds = ['bold', 'italic', 'strikeThrough', 'insertUnorderedList'];
    cmds.forEach(function(cmd) {
      var btn = toolbar.querySelector('button[data-cmd="' + cmd + '"]');
      if (btn) {
        btn.classList.toggle('active', document.queryCommandState(cmd));
      }
    });
  }

  function showToolbar(sectionEl) {
    activeSection = sectionEl;
    createToolbar();
    toolbar.style.display = 'flex';
    // Position after a frame so the element dimensions are settled
    requestAnimationFrame(function() { positionToolbar(sectionEl); });
  }

  function hideToolbar() {
    if (toolbar) {
      toolbar.style.display = 'none';
      closeHlGroup();
    }
    activeSection = null;
  }

  // Selection change → update button states
  document.addEventListener('selectionchange', function() {
    if (activeSection) updateToolbarState();
  });

  // Expose to parent
  window.__bfaEditor = {
    showToolbar: showToolbar,
    hideToolbar: hideToolbar,
    positionToolbar: positionToolbar,
  };
})();
`

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

    // Inject editor styles
    const style = doc.createElement('style')
    style.textContent = IFRAME_EDITOR_STYLES
    doc.head.appendChild(style)

    // Inject editor script
    const script = doc.createElement('script')
    script.textContent = IFRAME_EDITOR_SCRIPT
    doc.body.appendChild(script)

    // Section click → notify parent
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
    const iframeWin = iframeRef.current?.contentWindow as any

    // Close previous edit
    if (editingSection) {
      const prev = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
      if (prev) {
        prev.contentEditable = 'false'
        prev.classList.remove('editing')
        prev.innerHTML = originalHtmlRef.current
      }
      iframeWin?.__bfaEditor?.hideToolbar()
    }

    const el = doc.querySelector(`[data-section="${secName}"]`) as HTMLElement | null
    if (!el) return

    originalHtmlRef.current = el.innerHTML
    el.contentEditable = 'true'
    el.classList.add('editing')
    el.focus()
    setEditingSection(secName)

    // Show toolbar inside iframe
    iframeWin?.__bfaEditor?.showToolbar(el)

    requestAnimationFrame(resizeIframe)
  }, [editingSection, resizeIframe])

  const cancelEdit = useCallback(() => {
    const doc = iframeRef.current?.contentDocument
    const iframeWin = iframeRef.current?.contentWindow as any
    if (!doc || !editingSection) return

    const el = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
    if (el) {
      el.contentEditable = 'false'
      el.classList.remove('editing')
      el.innerHTML = originalHtmlRef.current
    }
    iframeWin?.__bfaEditor?.hideToolbar()
    setEditingSection(null)
  }, [editingSection])

  const saveEdit = useCallback(async () => {
    const doc = iframeRef.current?.contentDocument
    const iframeWin = iframeRef.current?.contentWindow as any
    if (!doc || !editingSection) return
    const el = doc.querySelector(`[data-section="${editingSection}"]`) as HTMLElement | null
    if (!el) return

    setSaving(true)
    try {
      await onSaveSection(editingSection, el.innerHTML)
      el.contentEditable = 'false'
      el.classList.remove('editing')
      iframeWin?.__bfaEditor?.hideToolbar()
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
            Editing: <b>{editingSection}</b>
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
