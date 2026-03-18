import { createRoot } from 'react-dom/client'
import { BfaTodoPage } from '@/pages/bfa-todo/BfaTodoPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<BfaTodoPage />)
