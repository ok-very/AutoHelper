import { createRoot } from 'react-dom/client'
import { PolicyMatrixPage } from '@/pages/system/PolicyMatrixPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<PolicyMatrixPage />)
