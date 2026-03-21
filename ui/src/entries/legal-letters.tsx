import { createRoot } from 'react-dom/client'
import { LegalLettersPage } from '@/pages/legal-letters/LegalLettersPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<LegalLettersPage />)
