import { createRoot } from 'react-dom/client'
import { HomePage } from '@/pages/home/HomePage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<HomePage />)
