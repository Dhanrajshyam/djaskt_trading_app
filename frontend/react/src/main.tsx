import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'
import { RequireAuth } from './features/auth/RequireAuth.tsx'
import IndexRedirect from './pages/IndexRedirect.tsx'
import LoginPage from './pages/LoginPage.tsx'
import SignupPage from './pages/SignupPage.tsx'
import DashboardPage from './pages/DashboardPage.tsx'
import PortfolioPage from './pages/PortfolioPage.tsx'
import BrokerageSetupPage from './pages/BrokerageSetupPage.tsx'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<App />}>
            <Route path="/" element={<IndexRedirect />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route
              path="/dashboard"
              element={
                <RequireAuth>
                  <DashboardPage />
                </RequireAuth>
              }
            />
            <Route
              path="/portfolio"
              element={
                <RequireAuth>
                  <PortfolioPage />
                </RequireAuth>
              }
            />
            <Route
              path="/brokerage-setup"
              element={
                <RequireAuth>
                  <BrokerageSetupPage />
                </RequireAuth>
              }
            />
            <Route path="*" element={<IndexRedirect />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
