import { createRoot } from 'react-dom/client'
import { AnalyticsPage } from '@/pages/analytics/AnalyticsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<AnalyticsPage />)
