import type { ReactNode } from 'react'
import { MousePointerClick, Link2 } from 'lucide-react'

const ICONS: Record<string, (size: number) => ReactNode> = {
  google: (size) => (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  ),
  monday: (size) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="4.5" cy="17.5" r="3" fill="#FF3D57"/>
      <circle cx="12" cy="11" r="3" fill="#FFCB00"/>
      <circle cx="19.5" cy="17.5" r="3" fill="#00CA72"/>
      <rect x="3" y="6" width="3" height="12" rx="1.5" fill="#FF3D57"/>
      <rect x="10.5" y="4" width="3" height="8" rx="1.5" fill="#FFCB00"/>
      <rect x="18" y="8" width="3" height="10" rx="1.5" fill="#00CA72"/>
    </svg>
  ),
  exchange: (size) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="2" y="4" width="20" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      <path d="M2 8l10 6 10-6" stroke="currentColor" strokeWidth="1.5" fill="none"/>
    </svg>
  ),
  clickup: (size) => <MousePointerClick size={size} />,
  autoart: (size) => <Link2 size={size} />,
}

export function ProviderIcon({ provider, size = 18 }: { provider: string; size?: number }) {
  const render = ICONS[provider]
  if (!render) return null
  return render(size)
}
