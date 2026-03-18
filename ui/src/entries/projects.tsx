import { createRoot } from 'react-dom/client'
import { ProjectsPage } from '@/pages/projects/ProjectsPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<ProjectsPage />)
