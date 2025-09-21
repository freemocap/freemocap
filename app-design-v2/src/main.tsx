import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import AppContent from './AppContent.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppContent />
  </StrictMode>,
)
