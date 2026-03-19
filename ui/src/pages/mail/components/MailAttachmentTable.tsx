import { Paperclip, FileText, Image, File, ExternalLink } from 'lucide-react'
import type { Attachment } from '../types'

interface MailAttachmentTableProps {
  attachments: Attachment[]
  selectedIds: Set<string>
  onSelectionChange: (selectedIds: Set<string>) => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getFileIcon(contentType: string) {
  if (contentType.startsWith('image/')) return Image
  if (contentType.includes('pdf') || contentType.includes('document')) return FileText
  return File
}

function getTypeLabel(contentType: string): string {
  const typeMap: Record<string, string> = {
    'application/pdf': 'PDF',
    'image/jpeg': 'JPEG',
    'image/png': 'PNG',
    'image/heic': 'HEIC',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
    'text/csv': 'CSV',
    'text/plain': 'TXT',
  }
  return typeMap[contentType] || contentType.split('/').pop()?.toUpperCase() || 'FILE'
}

export function MailAttachmentTable({ attachments, selectedIds, onSelectionChange }: MailAttachmentTableProps) {
  const allSelected = attachments.length > 0 && attachments.every(a => selectedIds.has(a.id))
  const someSelected = attachments.some(a => selectedIds.has(a.id))

  const toggleAll = () => {
    onSelectionChange(allSelected ? new Set() : new Set(attachments.map(a => a.id)))
  }

  const toggleOne = (id: string) => {
    const next = new Set(selectedIds)
    next.has(id) ? next.delete(id) : next.add(id)
    onSelectionChange(next)
  }

  if (attachments.length === 0) return null

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: '4px', overflow: 'hidden', background: 'var(--bg-white)' }}>
      <div style={{ padding: '8px 16px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Paperclip size={14} style={{ color: 'var(--fg-disabled)' }} />
        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--fg-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Attachments ({attachments.length})
        </span>
      </div>
      <table style={{ width: '100%', fontSize: '13px', fontFamily: 'var(--font-sans)' }}>
        <thead style={{ background: 'var(--bg)', fontSize: '11px', color: 'var(--fg-disabled)', textTransform: 'uppercase' }}>
          <tr>
            <th style={{ width: 40, padding: '6px 12px', textAlign: 'left' }}>
              <input
                type="checkbox"
                checked={allSelected}
                ref={input => { if (input) input.indeterminate = someSelected && !allSelected }}
                onChange={toggleAll}
                style={{ accentColor: 'var(--accent)' }}
              />
            </th>
            <th style={{ padding: '6px 12px', textAlign: 'left' }}>Name</th>
            <th style={{ width: 80, padding: '6px 12px', textAlign: 'left' }}>Type</th>
            <th style={{ width: 96, padding: '6px 12px', textAlign: 'right' }}>Size</th>
            <th style={{ width: 40 }}></th>
          </tr>
        </thead>
        <tbody>
          {attachments.map(att => {
            const Icon = getFileIcon(att.contentType)
            const isSelected = selectedIds.has(att.id)
            return (
              <tr
                key={att.id}
                style={{
                  borderBottom: '1px solid var(--bg-surface)',
                  background: isSelected ? 'rgba(63, 92, 110, 0.04)' : undefined,
                }}
              >
                <td style={{ padding: '6px 12px' }}>
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleOne(att.id)}
                    style={{ accentColor: 'var(--accent)' }}
                  />
                </td>
                <td style={{ padding: '6px 12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Icon size={14} style={{ color: 'var(--fg-disabled)', flexShrink: 0 }} />
                    <span style={{ fontWeight: 500, color: 'var(--fg)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }} title={att.filename}>
                      {att.filename}
                    </span>
                  </div>
                </td>
                <td style={{ padding: '6px 12px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--fg-secondary)', background: 'var(--bg-surface)', padding: '2px 8px', borderRadius: '2px' }}>
                    {getTypeLabel(att.contentType)}
                  </span>
                </td>
                <td style={{ padding: '6px 12px', textAlign: 'right', color: 'var(--fg-secondary)' }}>
                  {formatFileSize(att.size)}
                </td>
                <td style={{ padding: '6px 12px' }}>
                  {att.localPath && (
                    <a
                      href={`file:///${att.localPath.replace(/\\/g, '/')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--accent)' }}
                      title="Open file"
                    >
                      <ExternalLink size={14} />
                    </a>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
