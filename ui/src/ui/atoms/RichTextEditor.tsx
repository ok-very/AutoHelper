import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Highlight from '@tiptap/extension-highlight'
import TextAlign from '@tiptap/extension-text-align'
import { TextStyle } from '@tiptap/extension-text-style'
import { clsx } from 'clsx'
import { useEffect, useRef } from 'react'

import { FontSize } from './tiptap-extensions/FontSize'
import { RichTextToolbar } from './RichTextToolbar'

export interface RichTextEditorProps {
  content: string
  onChange?: (html: string) => void
  editable?: boolean
  toolbar?: boolean
  className?: string
}

export function RichTextEditor({
  content,
  onChange,
  editable = true,
  toolbar = true,
  className,
}: RichTextEditorProps) {
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: false,
        codeBlock: false,
        code: false,
        blockquote: false,
        horizontalRule: false,
      }),
      Highlight.configure({ multicolor: true }),
      TextStyle,
      TextAlign.configure({
        types: ['paragraph'],
        alignments: ['left', 'center', 'right', 'justify'],
      }),
      FontSize,
    ],
    content,
    editable,
    onUpdate: ({ editor: e }) => {
      onChangeRef.current?.(e.getHTML())
    },
    editorProps: {
      attributes: {
        class: 'outline-none',
        style: [
          'font-family: Calibri, sans-serif',
          'font-size: 11pt',
          'line-height: 1.5',
          'color: var(--ws-fg)',
        ].join(';'),
      },
    },
  })

  // Sync editable prop
  useEffect(() => {
    if (editor && editor.isEditable !== editable) {
      editor.setEditable(editable)
    }
  }, [editor, editable])

  // Sync content when it changes externally (not from user edits)
  const isExternalUpdate = useRef(false)
  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      isExternalUpdate.current = true
      editor.commands.setContent(content, { emitUpdate: false })
      isExternalUpdate.current = false
    }
  }, [editor, content])

  return (
    <div
      className={clsx(
        'rounded',
        editable && 'focus-within:ring-1 focus-within:ring-[var(--ws-accent)]',
        className
      )}
      style={{ background: 'transparent' }}
    >
      {toolbar && editable && <RichTextToolbar editor={editor} />}
      <EditorContent
        editor={editor}
        className="px-2 py-1"
      />
    </div>
  )
}
