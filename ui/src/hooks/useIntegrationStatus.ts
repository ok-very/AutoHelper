import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import type { IntegrationStatus } from '@/lib/api'

export function useIntegrationStatus() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null)

  const refresh = useCallback(() => {
    api.integrations.status().then(setStatus).catch(() => {})
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // Auto-refresh when any OAuth popup completes
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      if (e.data?.ok && typeof e.data?.type === 'string' && e.data.type.endsWith('-oauth')) {
        refresh()
      }
    }
    window.addEventListener('message', handler)
    return () => window.removeEventListener('message', handler)
  }, [refresh])

  return { status, refresh }
}
