import { createRoot } from 'react-dom/client'
import { ReconPage } from '@/pages/recon/ReconPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<ReconPage />)
