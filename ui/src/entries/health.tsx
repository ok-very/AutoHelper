import { createRoot } from 'react-dom/client'
import { HealthPage } from '@/pages/health/HealthPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<HealthPage />)
