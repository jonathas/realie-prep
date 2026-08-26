import { BarChart3, BookOpenCheck, Menu, Settings, X } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { AdminPage } from './pages/AdminPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { QuizPage } from './pages/QuizPage'
import { StatsPage } from './pages/StatsPage'

const nav = [
  { to: '/', label: 'Study', icon: BookOpenCheck },
  { to: '/stats', label: 'Progress', icon: BarChart3 },
  { to: '/admin', label: 'Admin', icon: Settings },
]

export default function App() {
  const [open, setOpen] = useState(false)
  return <div className="min-h-screen">
    <header className="sticky top-0 z-20 border-b border-black/5 bg-cream/90 backdrop-blur-xl">
      <div className="mx-auto flex h-18 max-w-6xl items-center justify-between px-5 py-4 lg:px-8">
        <Link to="/" className="flex items-center gap-3" onClick={() => setOpen(false)}>
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-sage-700 font-serif text-xl text-white">Ř</span>
          <div><div className="font-serif text-xl font-bold leading-none">RealiePrep</div><div className="mt-1 text-[10px] font-semibold uppercase tracking-[.14em] text-black/45">Czech citizenship</div></div>
        </Link>
        <nav className="hidden items-center gap-1 md:flex">
          {nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition ${isActive ? 'bg-white text-sage-700 shadow-sm' : 'text-black/55 hover:text-ink'}`}><Icon size={17}/>{label}</NavLink>)}
        </nav>
        <button className="rounded-lg p-2 md:hidden" aria-label="Toggle menu" onClick={() => setOpen(!open)}>{open ? <X/> : <Menu/>}</button>
      </div>
      {open && <nav className="border-t border-black/5 bg-cream px-5 py-3 md:hidden">{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-xl px-3 py-3 font-semibold"><Icon size={18}/>{label}</NavLink>)}</nav>}
    </header>
    <main><Routes><Route path="/" element={<QuizPage/>}/><Route path="/stats" element={<StatsPage/>}/><Route path="/admin" element={<AdminPage/>}/><Route path="*" element={<NotFoundPage/>}/></Routes></main>
    <footer className="mx-auto max-w-6xl px-5 py-10 text-center text-sm text-black/40">RealiePrep · Your data stays on your server</footer>
  </div>
}
