import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../styles/tokens.css'
import '../index.css'
import ResearchPage from './ResearchPage.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ResearchPage />
  </StrictMode>,
)
