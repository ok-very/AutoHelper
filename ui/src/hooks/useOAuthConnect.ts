import { useState } from 'react'
import { openOAuthPopup } from '@/lib/oauth'
import { api } from '@/lib/api'

export function useOAuthConnect(onRefresh: () => void) {
  const [feedback, setFeedback] = useState('')
  const [feedbackErr, setFeedbackErr] = useState(false)

  const connect = async (
    provider: string,
    fetchAuth: () => Promise<{ url: string }>,
    messageType: string,
  ): Promise<boolean> => {
    setFeedback('')
    const ok = await openOAuthPopup(fetchAuth, messageType)
    if (ok) {
      setFeedback(`Connected to ${provider}`)
      setFeedbackErr(false)
      onRefresh()
    } else {
      setFeedback(`${provider} connection cancelled or failed`)
      setFeedbackErr(true)
    }
    return ok
  }

  const disconnect = async (
    provider: string,
    tokenKey: string,
    accountKey: string,
  ): Promise<boolean> => {
    try {
      const patch: Record<string, string> = { [tokenKey]: '' }
      if (accountKey) patch[accountKey] = ''
      await api.config.save(patch)
      setFeedback(`Disconnected from ${provider}`)
      setFeedbackErr(false)
      onRefresh()
      return true
    } catch {
      setFeedback('Disconnect failed')
      setFeedbackErr(true)
      return false
    }
  }

  const clearFeedback = () => { setFeedback(''); setFeedbackErr(false) }

  return { connect, disconnect, feedback, feedbackErr, clearFeedback }
}
