/** Open an OAuth popup and return a promise that resolves on postMessage success. */
export function openOAuthPopup(
  fetchAuth: () => Promise<{ url: string }>,
  messageType: string,
): Promise<boolean> {
  return new Promise(async (resolve) => {
    try {
      const { url } = await fetchAuth()
      const popup = window.open(url, `${messageType}-popup`, 'width=600,height=700,popup=yes')

      const handler = (e: MessageEvent) => {
        if (e.data?.type === messageType) {
          window.removeEventListener('message', handler)
          resolve(e.data.ok === true)
        }
      }
      window.addEventListener('message', handler)

      // Fallback: if popup closes without postMessage
      const timer = setInterval(() => {
        if (popup && popup.closed) {
          clearInterval(timer)
          window.removeEventListener('message', handler)
          // Give a small delay for any in-flight postMessage
          setTimeout(() => resolve(false), 300)
        }
      }, 500)
    } catch {
      resolve(false)
    }
  })
}
