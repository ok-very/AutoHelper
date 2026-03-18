import { createRoot } from 'react-dom/client'
import { ContactsSettingsPage } from '@/pages/contacts-settings/ContactsSettingsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<ContactsSettingsPage />)
