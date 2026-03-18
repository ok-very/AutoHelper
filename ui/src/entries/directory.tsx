import { createRoot } from 'react-dom/client'
import { DirectoryPage } from '@/pages/directory/DirectoryPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<DirectoryPage />)
