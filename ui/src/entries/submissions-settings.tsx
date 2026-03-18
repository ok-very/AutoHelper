import { createRoot } from 'react-dom/client'
import { SubmissionsSettingsPage } from '@/pages/submissions-settings/SubmissionsSettingsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<SubmissionsSettingsPage />)
