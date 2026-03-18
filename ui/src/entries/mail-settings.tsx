import { createRoot } from 'react-dom/client'
import { MailSettingsPage } from '@/pages/mail-settings/MailSettingsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<MailSettingsPage />)
