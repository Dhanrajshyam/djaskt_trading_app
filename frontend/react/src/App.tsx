import { Outlet } from 'react-router'
import { Header } from './components/layout/Header'
import { Footer } from './components/layout/Footer'

/** Top-level layout: every page renders inside this shell via <Outlet/>. */
export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 flex flex-col">
      <Header />
      <main className="max-w-7xl mx-auto w-full px-4 py-6 flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
