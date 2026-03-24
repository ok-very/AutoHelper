import { clsx } from 'clsx'
import type { Editor } from '@tiptap/react'
import {
  Bold, Italic, Strikethrough, List, AlignLeft, AlignCenter,
  AlignRight, AlignJustify, Highlighter,
} from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

interface RichTextToolbarProps {
  editor: Editor | null
  className?: string
}

const HIGHLIGHT_COLORS = [
  { label: 'Yellow', value: '#FFF3B0' },
  { label: 'Green', value: '#D4EDBC' },
  { label: 'Cyan', value: '#B5E8EC' },
] as const

const FONT_SIZES = ['8pt', '11pt'] as const

function ToolbarButton({
  active, onClick, title, children,
}: {
  active?: boolean
  onClick: () => void
  title: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onMouseDown={(e) => { e.preventDefault(); onClick() }}
      title={title}
      className={clsx(
        'inline-flex items-center justify-center rounded p-1 transition-colors',
        'hover:bg-[rgba(63,92,110,0.08)]',
        active && 'bg-[rgba(63,92,110,0.1)]'
      )}
      style={{ width: 24, height: 24 }}
    >
      {children}
    </button>
  )
}

function Divider() {
  return <span className="mx-0.5 h-4 w-px bg-[var(--ws-group-border)]" />
}

export function RichTextToolbar({ editor, className }: RichTextToolbarProps) {
  const [highlightOpen, setHighlightOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setHighlightOpen(false)
      }
    }
    if (highlightOpen) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [highlightOpen])

  if (!editor) return null

  const iconSize = 13
  const iconProps = { size: iconSize, strokeWidth: 1.5 }
  const secondaryColor = 'var(--ws-text-secondary)'

  return (
    <div
      className={clsx(
        'flex items-center gap-0.5 px-1.5 py-1 select-none',
        className
      )}
      style={{
        fontFamily: 'var(--font-sans)',
        fontSize: '11px',
        color: secondaryColor,
        borderBottom: '1px solid var(--ws-group-border)',
      }}
    >
      {/* Text formatting */}
      <ToolbarButton
        active={editor.isActive('bold')}
        onClick={() => editor.chain().focus().toggleBold().run()}
        title="Bold"
      >
        <Bold {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive('italic')}
        onClick={() => editor.chain().focus().toggleItalic().run()}
        title="Italic"
      >
        <Italic {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive('strike')}
        onClick={() => editor.chain().focus().toggleStrike().run()}
        title="Strikethrough"
      >
        <Strikethrough {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>

      <Divider />

      {/* Highlight dropdown */}
      <div className="relative" ref={dropdownRef}>
        <ToolbarButton
          active={editor.isActive('highlight')}
          onClick={() => setHighlightOpen(!highlightOpen)}
          title="Highlight"
        >
          <Highlighter {...iconProps} style={{ color: secondaryColor }} />
        </ToolbarButton>
        {highlightOpen && (
          <div
            className="absolute left-0 top-full z-50 mt-1 flex gap-1 rounded p-1.5"
            style={{
              background: 'var(--ws-panel-bg)',
              border: '1px solid var(--ws-group-border)',
              boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
            }}
          >
            {HIGHLIGHT_COLORS.map(({ label, value }) => (
              <button
                key={value}
                type="button"
                title={label}
                onMouseDown={(e) => {
                  e.preventDefault()
                  editor.chain().focus().toggleHighlight({ color: value }).run()
                  setHighlightOpen(false)
                }}
                className="rounded transition-opacity hover:opacity-80"
                style={{
                  width: 20,
                  height: 20,
                  background: value,
                  border: editor.isActive('highlight', { color: value })
                    ? '2px solid var(--ws-accent)'
                    : '1px solid var(--ws-group-border)',
                }}
              />
            ))}
            <button
              type="button"
              title="Remove highlight"
              onMouseDown={(e) => {
                e.preventDefault()
                editor.chain().focus().unsetHighlight().run()
                setHighlightOpen(false)
              }}
              className="rounded text-xs transition-opacity hover:opacity-80"
              style={{
                width: 20,
                height: 20,
                border: '1px solid var(--ws-group-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: secondaryColor,
                fontSize: '10px',
              }}
            >
              &times;
            </button>
          </div>
        )}
      </div>

      <Divider />

      {/* Bullet list */}
      <ToolbarButton
        active={editor.isActive('bulletList')}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        title="Bullet list"
      >
        <List {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>

      <Divider />

      {/* Font size */}
      <select
        value={
          editor.isActive('fontSize', { size: '8pt' }) ? '8pt' :
          editor.isActive('fontSize', { size: '11pt' }) ? '11pt' : ''
        }
        onChange={(e) => {
          const size = e.target.value
          if (size) {
            editor.chain().focus().setFontSize(size).run()
          } else {
            editor.chain().focus().unsetFontSize().run()
          }
        }}
        className="rounded px-1 py-0.5"
        style={{
          fontSize: '10px',
          color: secondaryColor,
          background: 'transparent',
          border: '1px solid var(--ws-group-border)',
          outline: 'none',
          cursor: 'pointer',
        }}
        title="Font size"
      >
        <option value="">Size</option>
        {FONT_SIZES.map(s => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>

      <Divider />

      {/* Alignment */}
      <ToolbarButton
        active={editor.isActive({ textAlign: 'left' })}
        onClick={() => editor.chain().focus().setTextAlign('left').run()}
        title="Align left"
      >
        <AlignLeft {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive({ textAlign: 'center' })}
        onClick={() => editor.chain().focus().setTextAlign('center').run()}
        title="Align center"
      >
        <AlignCenter {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive({ textAlign: 'right' })}
        onClick={() => editor.chain().focus().setTextAlign('right').run()}
        title="Align right"
      >
        <AlignRight {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive({ textAlign: 'justify' })}
        onClick={() => editor.chain().focus().setTextAlign('justify').run()}
        title="Justify"
      >
        <AlignJustify {...iconProps} style={{ color: secondaryColor }} />
      </ToolbarButton>
    </div>
  )
}
