import type { IntegrationStatus } from '@/lib/api'

export interface Diagnosis {
  summary: string
  healthy: boolean
  callbackPath?: string
  account?: string
}

function tryPathname(uri?: string): string | undefined {
  if (!uri) return undefined
  try { return new URL(uri).pathname } catch { return uri }
}

export function diagnoseProvider(
  providerId: string,
  status: IntegrationStatus | null,
): Diagnosis {
  if (!status) return { summary: '\u2014', healthy: false }

  switch (providerId) {
    case 'google': {
      const g = status.google
      if (!g.oauth_available) return { summary: 'Client ID missing in .env', healthy: false }
      if (!g.configured) return { summary: 'Not connected', healthy: false, callbackPath: tryPathname(g.redirect_uri) }
      return {
        summary: g.has_refresh_token ? 'Connected, auto-renewing' : 'Connected, may expire',
        healthy: true,
        callbackPath: tryPathname(g.redirect_uri),
        account: g.account,
      }
    }
    case 'clickup': {
      const c = status.clickup
      if (!c.configured && !c.oauth_available) return { summary: 'Not configured', healthy: false }
      if (!c.configured) return { summary: 'Not connected', healthy: false, callbackPath: tryPathname(c.redirect_uri) }
      const source = c.source === 'env' ? 'Connected via .env' : 'Connected via OAuth'
      return { summary: source, healthy: true, callbackPath: tryPathname(c.redirect_uri) }
    }
    case 'monday': {
      const m = status.monday
      if (!m.oauth_available) return { summary: 'Client ID missing in .env', healthy: false }
      if (!m.configured) return { summary: 'Not connected', healthy: false, callbackPath: tryPathname(m.redirect_uri) }
      return { summary: 'Connected', healthy: true, callbackPath: tryPathname(m.redirect_uri), account: m.account }
    }
    case 'exchange': {
      const e = status.exchange
      if (!e.configured) return { summary: 'Not configured', healthy: false }
      const source = e.source === 'env' ? 'Credentials from .env' : 'Credentials from config'
      return { summary: source, healthy: true, account: e.email?.value }
    }
    case 'autoart': {
      const a = status.autoart
      if (!a?.paired) return { summary: 'Not paired', healthy: false }
      return { summary: 'Paired', healthy: true }
    }
    default:
      return { summary: '\u2014', healthy: false }
  }
}
