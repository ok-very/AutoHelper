/** Open an OAuth popup and resolve when connected (via postMessage or validation poll). */
export function openOAuthPopup(
  fetchAuth: () => Promise<{ url: string }>,
  messageType: string,
): Promise<boolean> {
  return new Promise(async (resolve) => {
    try {
      const { url } = await fetchAuth()
      const popup = window.open(url, `${messageType}-popup`, 'width=600,height=700,popup=yes')
      let resolved = false

      const done = (ok: boolean) => {
        if (resolved) return
        resolved = true
        window.removeEventListener('message', handler)
        resolve(ok)
      }

      // Path 1: postMessage from callback page (works when no redirect breaks opener)
      const handler = (e: MessageEvent) => {
        if (e.data?.type === messageType) done(e.data.ok === true)
      }
      window.addEventListener('message', handler)

      // Path 2: poll for connection after popup closes (handles redirect-based OAuth)
      const timer = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(timer)
          // Give postMessage a moment, then poll the validate endpoint
          setTimeout(async () => {
            if (resolved) return
            try {
              const r = await fetch('/clickup/validate')
              const data = await r.json()
              done(data.ok === true)
            } catch {
              done(false)
            }
          }, 500)
        }
      }, 500)
    } catch {
      resolve(false)
    }
  })
}
