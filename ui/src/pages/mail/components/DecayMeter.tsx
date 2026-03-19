import { useState, useEffect } from 'react'

interface DecayMeterProps {
  timestamp: string
  maxHours?: number
}

export function DecayMeter({ timestamp, maxHours = 48 }: DecayMeterProps) {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60000)
    return () => clearInterval(timer)
  }, [])

  const receivedTime = new Date(timestamp).getTime()
  const hoursElapsed = (now - receivedTime) / (1000 * 60 * 60)
  const percentage = Math.min(100, (hoursElapsed / maxHours) * 100)

  let color = 'var(--color-success)'
  let label = 'Fresh'
  if (hoursElapsed > 48) {
    color = 'var(--color-error)'
    label = 'Overdue'
  } else if (hoursElapsed > 24) {
    color = 'var(--color-warning)'
    label = 'Aging'
  }

  return (
    <div className="flex flex-col gap-0.5 w-full max-w-[80px]" title={label}>
      <div className="flex justify-between items-center" style={{ fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        <span style={{ color }}>{Math.round(hoursElapsed)}h</span>
      </div>
      <div style={{ height: '6px', width: '100%', background: 'var(--bg-surface)', borderRadius: '3px', overflow: 'hidden' }}>
        <div
          style={{
            height: '100%', borderRadius: '3px',
            background: color,
            width: `${percentage}%`,
            transition: 'width 0.5s',
          }}
        />
      </div>
    </div>
  )
}
