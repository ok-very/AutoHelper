import type { ReactNode } from 'react'
import { CardShell } from '@/components/settings/CardShell'
import { StatusBadge } from '@/components/settings/StatusBadge'
import { ProviderIcon } from './ProviderIcon'
import { SourceBadge } from './SourceBadge'
import { CapabilityFlags } from './CapabilityFlags'
import type { ProviderDef, SourceType } from './registry'
import './IntegrationCard.css'

export interface IntegrationCardProps {
  provider: ProviderDef
  connected: boolean
  source?: SourceType
  account?: string
  capabilities?: string[]
  variant?: 'full' | 'compact'
  onConnect?: () => void
  onDisconnect?: () => void
  onTest?: () => void
  children?: ReactNode
}

export function IntegrationCard({
  provider,
  connected,
  source,
  account,
  capabilities,
  variant = 'full',
  onConnect,
  onDisconnect,
  onTest,
  children,
}: IntegrationCardProps) {
  const caps = capabilities
    ? provider.capabilities.filter(c => capabilities.includes(c.key))
    : provider.capabilities

  if (variant === 'compact') {
    return (
      <span className="integration-card-compact">
        <span className="integration-card-compact-name">{provider.name}</span>
        <CapabilityFlags capabilities={caps} />
        {connected ? (
          <>
            <StatusBadge ok label="Connected" />
            {account && <span className="integration-card-compact-account">{account}</span>}
            {onDisconnect && (
              <button className="btn btn-sm" style={{ fontSize: '11px' }} onClick={onDisconnect}>
                Disconnect
              </button>
            )}
          </>
        ) : onConnect ? (
          <button className="btn btn-sm btn-primary" onClick={onConnect}>Connect</button>
        ) : (
          <span className="not-configured">Not configured</span>
        )}
      </span>
    )
  }

  // Full variant — build a subtitle line with flags + source + account
  const hasActions = (connected && (onDisconnect || onTest)) || (!connected && onConnect)

  return (
    <CardShell
      icon={<ProviderIcon provider={provider.id} />}
      iconBg={provider.iconColor}
      title={provider.name}
      badge={<StatusBadge ok={connected} label={connected ? 'Connected' : 'Not connected'} />}
      subtitle={connected && account ? `Connected as ${account}` : undefined}
    >
      <div className="integration-card-meta">
        <CapabilityFlags capabilities={caps} />
        <SourceBadge source={source} />
      </div>
      {hasActions && (
        <div className="integration-card-actions">
          {connected ? (
            <>
              {onDisconnect && (
                <button className="btn btn-sm" onClick={onDisconnect}>Disconnect</button>
              )}
              {onTest && (
                <button className="btn btn-sm" onClick={onTest}>Test</button>
              )}
            </>
          ) : onConnect ? (
            <button className="btn btn-sm btn-primary" onClick={onConnect}>Connect</button>
          ) : null}
        </div>
      )}
      {children && (
        <div className="integration-card-expanded">{children}</div>
      )}
    </CardShell>
  )
}
