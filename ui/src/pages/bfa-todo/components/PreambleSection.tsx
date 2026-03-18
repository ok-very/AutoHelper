import { clsx } from 'clsx'
import { ChevronRight } from 'lucide-react'
import { Badge } from '@ui/atoms'
import { api } from '@/lib/api'
import { IframeCompositionView } from './IframeCompositionView'
import type { BfaTodoPreamble } from '../types'

interface PreambleSectionProps {
  preambles: BfaTodoPreamble[]
  preambleExpanded: Set<string>
  onTogglePreambleExpanded: (uid: string) => void
}

function PreambleCompositionView({ uid }: { uid: string }) {
  return (
    <IframeCompositionView
      uid={uid}
      fetchUrl={`/api/bfa-todo/preambles/${uid}/html`}
      onSaveSection={(sectionName, html) => api.bfaTodo.updatePreambleSection(uid, sectionName, html)}
      title={`Preamble ${uid}`}
    />
  )
}

export function PreambleSection({ preambles, preambleExpanded, onTogglePreambleExpanded }: PreambleSectionProps) {
  if (preambles.length === 0) return null

  return (
    <div style={{ border: '1px solid var(--border)' }}>
      <div className="flex items-center gap-2 px-3 py-1.5" style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)', fontFamily: 'var(--font-sans)', fontSize: '11px', color: 'var(--fg-secondary)' }}>
        <span style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Preamble
        </span>
      </div>
      {preambles.map(pre => (
        <div key={pre.uid} style={{ borderBottom: '1px solid var(--border)' }}>
          <div
            className="flex items-center gap-2"
            style={{ padding: '6px 12px', cursor: 'pointer', fontFamily: 'var(--font-sans)' }}
            onClick={() => onTogglePreambleExpanded(pre.uid)}
          >
            <ChevronRight
              size={14}
              className={clsx('transition-transform shrink-0', preambleExpanded.has(pre.uid) && 'rotate-90')}
              style={{ color: 'var(--fg-secondary)' }}
            />
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--fg)' }}>
              {pre.title}
            </span>
            <Badge variant="neutral" size="xs">{pre.type === 'preamble' ? 'overview' : 'lists'}</Badge>
          </div>
          {preambleExpanded.has(pre.uid) && (
            <PreambleCompositionView uid={pre.uid} />
          )}
        </div>
      ))}
    </div>
  )
}
