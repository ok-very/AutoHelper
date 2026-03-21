import { useState, useCallback } from 'react'
import { Copy, Check } from 'lucide-react'
import { clsx } from 'clsx'

interface CopyButtonProps {
  value: string
  className?: string
  size?: number
}

export function CopyButton({ value, className, size = 14 }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)

  const copy = useCallback(() => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }, [value])

  return (
    <button
      type="button"
      onClick={copy}
      className={clsx(
        'inline-flex items-center justify-center rounded p-1 transition-colors',
        'text-ws-text-secondary hover:text-ws-fg hover:bg-ws-row-expanded-bg',
        'focus:outline-none',
        className,
      )}
      title="Copy"
    >
      {copied ? <Check size={size} /> : <Copy size={size} />}
    </button>
  )
}
