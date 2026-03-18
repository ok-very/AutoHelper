import { useState } from 'react'

interface ConnectedValueProps {
  value: string
  placeholder?: string
  password?: boolean
  onSave: (value: string) => Promise<void>
  onClear?: () => Promise<void>
}

export function ConnectedValue({ value, placeholder, password, onSave, onClear }: ConnectedValueProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const [saving, setSaving] = useState(false)

  const isSet = value.length > 0

  if (editing) {
    return (
      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flex: 1 }}>
        <input
          type={password ? 'password' : 'text'}
          className="setting-input"
          value={draft}
          onChange={e => setDraft(e.target.value)}
          placeholder={placeholder}
          style={{ flex: 1 }}
          autoFocus
        />
        <button
          className="btn btn-primary btn-sm"
          disabled={saving}
          onClick={async () => {
            setSaving(true)
            await onSave(draft)
            setSaving(false)
            setEditing(false)
          }}
        >
          Save
        </button>
        <button
          className="btn btn-sm"
          onClick={() => { setDraft(value); setEditing(false) }}
        >
          Cancel
        </button>
      </div>
    )
  }

  if (isSet) {
    return (
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flex: 1 }}>
        <span className="configured-value">
          {password ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : value}
        </span>
        <button className="btn btn-sm btn-ghost" onClick={() => { setDraft(password ? '' : value); setEditing(true) }}>
          Edit
        </button>
        {onClear && (
          <button className="btn btn-sm btn-ghost" style={{ color: 'var(--color-error)' }} onClick={onClear}>
            Clear
          </button>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flex: 1 }}>
      <span className="not-configured">Not configured</span>
      <button className="btn btn-sm" onClick={() => { setDraft(''); setEditing(true) }}>
        Configure
      </button>
    </div>
  )
}
