import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import type { MailEmail } from '../types'
import { hydrateEmail } from '../types'

export function useMailInbox(params?: { project_id?: string }) {
  const [emails, setEmails] = useState<MailEmail[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  const load = useCallback(() => {
    setLoading(true)
    const qs = new URLSearchParams()
    if (params?.project_id) qs.set('project_id', params.project_id)
    qs.set('limit', '200')

    fetch(`/mail/emails?${qs}`)
      .then(r => r.ok ? r.json() : { emails: [], total: 0 })
      .then(data => {
        setEmails((data.emails ?? []).map(hydrateEmail))
        setTotal(data.total ?? 0)
      })
      .catch(() => { setEmails([]); setTotal(0) })
      .finally(() => setLoading(false))
  }, [params?.project_id])

  useEffect(() => { load() }, [load])

  return { emails, loading, total, reload: load }
}
