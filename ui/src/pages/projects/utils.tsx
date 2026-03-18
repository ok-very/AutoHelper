import { Card, Spinner } from '@ui/atoms'
import type { BudgetCalculation } from '@/lib/types'

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

export function BudgetCard({ budget, loading }: { budget: BudgetCalculation | null; loading: boolean }) {
  if (loading) {
    return (
      <Card padding="md">
        <div className="flex items-center gap-2 text-sm text-ws-text-secondary">
          <Spinner size="sm" />
          <span>Calculating budget...</span>
        </div>
      </Card>
    )
  }
  if (!budget) return null

  return (
    <Card padding="md">
      <h3 className="text-xs font-semibold text-ws-text-secondary uppercase tracking-wide mb-3">Budget</h3>
      <div className="flex flex-col gap-1.5 text-sm">
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Contribution rate</span>
          <span className="text-ws-fg tabular-nums">{formatPercent(budget.contribution_rate)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Eligible cost</span>
          <span className="text-ws-fg tabular-nums">{formatCurrency(budget.eligible_cost)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Art contribution</span>
          <span className="text-ws-fg tabular-nums">{formatCurrency(budget.art_contribution)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-ws-text-secondary">Maintenance reserve ({formatPercent(budget.maintenance_reserve_rate)})</span>
          <span className="text-ws-fg tabular-nums">{formatCurrency(budget.maintenance_reserve)}</span>
        </div>
        <div className="flex justify-between border-t border-ws-panel-border pt-1.5 mt-1">
          <span className="font-medium text-ws-fg">Total</span>
          <span className="font-semibold text-ws-fg tabular-nums">{formatCurrency(budget.total)}</span>
        </div>
      </div>
    </Card>
  )
}

export type { BudgetCalculation }
