import { createRoot } from 'react-dom/client'
import { MailPage } from '@/pages/mail/MailPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<MailPage />)
