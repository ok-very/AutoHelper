import { createRoot } from 'react-dom/client'
import { SettingsPage } from '@/pages/settings/SettingsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<SettingsPage />)
