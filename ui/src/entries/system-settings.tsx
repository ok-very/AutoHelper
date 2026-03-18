import { createRoot } from 'react-dom/client'
import { SystemSettingsPage } from '@/pages/system-settings/SystemSettingsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<SystemSettingsPage />)
