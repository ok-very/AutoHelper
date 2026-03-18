import { createRoot } from 'react-dom/client'
import { ProjectDetailPage } from '@/pages/projects/ProjectDetailPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<ProjectDetailPage />)
