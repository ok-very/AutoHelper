import { createRoot } from 'react-dom/client'
import { ArtCollectorPage } from '@/pages/art-collector/ArtCollectorPage'
import '@/styles/shared.css'

createRoot(document.getElementById('app')!).render(<ArtCollectorPage />)
