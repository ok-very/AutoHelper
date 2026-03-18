import { createRoot } from 'react-dom/client'
import { ContactsPage } from '@/pages/contacts/ContactsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<ContactsPage />)
