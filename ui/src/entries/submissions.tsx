import { createRoot } from 'react-dom/client'
import { SubmissionsApp } from '@/submissions/SubmissionsApp'
import '@/submissions/submissions.css'

createRoot(document.getElementById('app')!).render(<SubmissionsApp />)
