import { createRoot } from 'react-dom/client'
import { EmailTemplateMatrixPage } from '@/pages/system/EmailTemplateMatrixPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<EmailTemplateMatrixPage />)
