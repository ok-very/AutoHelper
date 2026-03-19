import { useState } from 'react'
import { useIntegrationStatus } from '@/hooks/useIntegrationStatus'
import { useOAuthConnect } from '@/hooks/useOAuthConnect'
import { api } from '@/lib/api'
import type { IntegrationStatus } from '@/lib/api'
import { diagnoseProvider } from './diagnose'
import { MODULE_DEPS } from './dependencies'
import { PROVIDERS } from './registry'
import './IntegrationCard.css'

const OAUTH_CONFIG: Record<string, {
  fetchAuth: () => Promise<{ url: string }>
  messageType: string
}> = {
  google: { fetchAuth: api.google.auth, messageType: 'google-oauth' },
  clickup: { fetchAuth: api.clickup.auth, messageType: 'clickup-oauth' },
  monday: { fetchAuth: api.monday.auth, messageType: 'monday-oauth' },
}

export function WiringManifest({ module, status: externalStatus }: {
  module: string
  status?: IntegrationStatus | null
}) {
  const deps = MODULE_DEPS[module]
  const internal = useIntegrationStatus()
  const status = externalStatus !== undefined ? externalStatus : internal.status
  const refresh = internal.refresh
  const oauth = useOAuthConnect(refresh)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  if (!deps || deps.length === 0) return null

  return (
    <div className="wiring-manifest">
      {deps.map(dep => {
        const provider = PROVIDERS[dep.provider]
        const diag = diagnoseProvider(dep.provider, status)
        const expanded = expandedRow === dep.provider
        const oauthCfg = OAUTH_CONFIG[dep.provider]

        return (
          <div key={dep.provider}>
            <div
              className="wiring-row"
              onClick={() => setExpandedRow(prev => prev === dep.provider ? null : dep.provider)}
            >
              <span className="wiring-provider">{provider?.name ?? dep.provider}</span>
              <span className="wiring-sep">{'\u2192'}</span>
              <span className="wiring-purpose">{dep.purpose}</span>
              <span className="wiring-sep">{'\u00b7'}</span>
              <span className="wiring-status">{diag.summary}</span>
            </div>
            {expanded && (
              <div className="wiring-detail">
                {diag.callbackPath && (
                  <div className="wiring-detail-row">
                    <span className="wiring-detail-label">callback</span>
                    <span className="wiring-detail-value">{diag.callbackPath}</span>
                  </div>
                )}
                {diag.account && (
                  <div className="wiring-detail-row">
                    <span className="wiring-detail-label">account</span>
                    <span className="wiring-detail-value">{diag.account}</span>
                  </div>
                )}
                {oauthCfg && !diag.healthy && (
                  <div className="wiring-detail-row">
                    <span className="wiring-detail-label" />
                    <span>
                      <button
                        className="btn btn-sm btn-primary"
                        style={{ fontSize: '11px' }}
                        onClick={(e) => {
                          e.stopPropagation()
                          oauth.connect(provider?.name ?? dep.provider, oauthCfg.fetchAuth, oauthCfg.messageType)
                        }}
                      >
                        Connect
                      </button>
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
