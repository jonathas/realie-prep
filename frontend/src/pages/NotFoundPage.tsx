import { ArrowLeft, MapPinOff } from 'lucide-react'
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return <section className="mx-auto max-w-2xl px-5 py-20 text-center">
    <div className="card p-10 sm:p-14">
      <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-sage-100 text-sage-700"><MapPinOff /></span>
      <p className="eyebrow mt-6">404</p>
      <h1 className="mt-2 font-serif text-4xl font-bold">Page not found</h1>
      <p className="mx-auto mt-3 max-w-md text-black/55">The page you requested does not exist or may have moved.</p>
      <Link className="btn-primary mt-7" to="/"><ArrowLeft size={18} />Back to Study</Link>
    </div>
  </section>
}
