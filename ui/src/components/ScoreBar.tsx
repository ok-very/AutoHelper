interface ScoreBarProps {
  score: number
  variant?: 'inline' | 'detail'
}

function level(pct: number): string {
  if (pct >= 80) return 'high'
  if (pct >= 40) return 'mid'
  return 'low'
}

export function ScoreBar({ score, variant = 'inline' }: ScoreBarProps) {
  const pct = Math.round(score * 100)
  const lvl = level(pct)

  if (variant === 'detail') {
    return (
      <div className="detail-score-bar">
        <div className={`detail-score-fill score-${lvl}`} style={{ width: `${pct}%` }} />
      </div>
    )
  }

  return (
    <span className="score-cell">
      <span className="score-bar">
        <span className={`score-fill score-${lvl}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="score-pct">{pct}%</span>
    </span>
  )
}
