import { CheckCircle2, Database, ExternalLink, LockKeyhole, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { ErrorState, Loading } from '../components/States'
import type { AdminStatus, ImportPreview } from '../types'

export function AdminPage() {
  const [status, setStatus] = useState<AdminStatus | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [password, setPassword] = useState(() => sessionStorage.getItem('adminPassword') ?? '')
  const load = useCallback(async () => { try { setError(null); setStatus(await api.get<AdminStatus>('/api/admin/status', true)) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load admin status') } }, [])
  useEffect(() => { void load() }, [load])
  const savePassword = () => { sessionStorage.setItem('adminPassword', password); void load() }
  const checkForUpdates = async () => {
    setBusy(true); setError(null)
    try { setPreview(await api.post<ImportPreview>('/api/admin/sync/preview', undefined, true)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not check the official question bank') }
    finally { setBusy(false) }
  }
  const confirm = async () => {
    if (!preview) return; setBusy(true)
    try { setStatus(await api.post<AdminStatus>(`/api/admin/sync/${preview.token}/confirm`, undefined, true)); setPreview(null) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Sync failed') }
    finally { setBusy(false) }
  }
  if (!status && !error) return <Loading/>
  if (!status && error === 'Invalid admin password') return <section className="mx-auto max-w-md px-5 py-20"><div className="card p-8"><LockKeyhole className="text-sage-700"/><h1 className="mt-5 font-serif text-3xl">Admin access</h1><p className="mt-2 text-sm text-black/50">Enter the password configured for this installation.</p><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-6 w-full rounded-xl border border-black/10 bg-white p-3" placeholder="Admin password"/><button onClick={savePassword} className="btn-primary mt-3 w-full">Continue</button></div></section>
  if (!status) return <ErrorState message={error!} retry={() => void load()}/>
  return <section className="mx-auto max-w-5xl px-5 py-10 lg:py-14">
    <p className="eyebrow">Administration</p><h1 className="mt-2 font-serif text-4xl font-bold sm:text-5xl">Question bank</h1><p className="mt-3 max-w-2xl text-black/50">The shipped bank is ready to study. Check the official NPI website for updates at any time; changes are validated and previewed before they replace your local bank.</p>
    {error && <div className="mt-6 rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
    <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
      <div className="card p-6 sm:p-8"><div className="flex items-center gap-3"><span className="rounded-xl bg-sage-100 p-3 text-sage-700"><Database/></span><div><p className="text-sm text-black/45">Active database</p><h2 className="font-serif text-2xl">{status.filename ?? 'No source synced'}</h2></div></div>{status.filename && <div className="mt-7 grid grid-cols-3 gap-3"><div className="rounded-xl bg-sage-50 p-4"><strong className="font-serif text-2xl">{status.question_count}</strong><p className="text-xs text-black/45">Questions</p></div><div className="rounded-xl bg-sage-50 p-4"><strong className="font-serif text-2xl">{status.category_count}</strong><p className="text-xs text-black/45">Topics</p></div><div className="rounded-xl bg-sage-50 p-4"><strong className="font-serif text-2xl">{status.option_count}</strong><p className="text-xs text-black/45">Options</p></div></div>}<dl className="mt-6 space-y-3 text-sm"><div className="flex justify-between gap-4"><dt className="text-black/45">Status</dt><dd className="flex items-center gap-1 font-semibold text-sage-700"><CheckCircle2 size={15}/>{status.validation_status ?? 'Ready'}</dd></div>{status.source_url && <div className="flex justify-between gap-4"><dt className="text-black/45">Source</dt><dd><a className="inline-flex items-center gap-1 text-sage-700 hover:underline" href={status.source_url} target="_blank" rel="noreferrer">Official website <ExternalLink size={13}/></a></dd></div>}{status.sha256 && <div className="flex justify-between gap-4"><dt className="text-black/45">Content hash</dt><dd className="max-w-[65%] truncate font-mono text-xs">{status.sha256}</dd></div>}{status.imported_at && <div className="flex justify-between"><dt className="text-black/45">Last synced</dt><dd>{new Date(status.imported_at).toLocaleDateString()}</dd></div>}</dl></div>
      <div className="card p-6 sm:p-8"><RefreshCw className={`text-sage-700 ${busy ? 'animate-spin' : ''}`} size={30}/><h2 className="mt-4 font-serif text-2xl">Check for updates</h2><p className="mt-2 text-sm leading-relaxed text-black/50">RealiePrep reads the official online database, downloads its visual assets, and validates all 300 questions and 30 topics. Your current bank stays untouched until you confirm.</p><button className="btn-secondary mt-6 w-full" disabled={busy} onClick={() => void checkForUpdates()}><RefreshCw size={17}/>{busy ? 'Checking official source…' : 'Check official source'}</button></div>
    </div>
    {preview && <div className="card mt-6 p-6 sm:p-8"><div className="flex items-center gap-3"><CheckCircle2 className={preview.valid ? 'text-sage-600' : 'text-red-600'}/><div><p className="eyebrow">Update preview</p><h2 className="font-serif text-2xl">{preview.filename}</h2></div></div><div className="mt-5 grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-sage-50 p-4"><strong>{preview.question_count} / 300</strong><p className="text-xs text-black/45">Questions</p></div><div className="rounded-xl bg-sage-50 p-4"><strong>{preview.category_count} / 30</strong><p className="text-xs text-black/45">Topics</p></div><div className="rounded-xl bg-sage-50 p-4"><strong>{preview.option_count}</strong><p className="text-xs text-black/45">Options</p></div></div>{preview.errors.length > 0 && <ul className="mt-4 list-disc pl-5 text-sm text-red-700">{preview.errors.map((item) => <li key={item}>{item}</li>)}</ul>}<p className="mt-5 text-sm text-amber-700">Confirming an update replaces the question bank and resets study progress so statistics remain consistent.</p><button className="btn-primary mt-4" disabled={!preview.valid || busy} onClick={() => void confirm()}>Confirm update</button></div>}
  </section>
}
