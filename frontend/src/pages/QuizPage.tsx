import { ArrowRight, Check, CircleAlert, RotateCcw, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { ErrorState, Loading } from '../components/States'
import type { Batch, BatchResult, MistakeType, OptionLabel, QuizSession, SelectionMode } from '../types'

const mistakeLabels: Record<MistakeType, string> = { vocabulary: 'Vocabulary', knowledge: "Didn't know", careless: 'Careless', unknown: 'Not sure' }
const optionLabels = new Set<OptionLabel>(['A', 'B', 'C', 'D'])
const draftKey = (sessionId: number, batchId: number) => `realieprep:draft:${sessionId}:${batchId}`

function readDraft(sessionId: number, batch: Batch): Record<number, OptionLabel> {
  try {
    const stored = JSON.parse(localStorage.getItem(draftKey(sessionId, batch.id)) ?? '{}') as Record<string, unknown>
    return Object.fromEntries(batch.questions.flatMap((question) => {
      const value = stored[String(question.id)]
      return typeof value === 'string' && optionLabels.has(value as OptionLabel) ? [[question.id, value as OptionLabel]] : []
    }))
  } catch {
    localStorage.removeItem(draftKey(sessionId, batch.id))
    return {}
  }
}

function savedResult(batch: Batch): BatchResult | undefined {
  if (!batch.submitted || batch.questions.some((question) => question.selected_option === null || question.correct_option === null || question.correct === null)) return undefined
  const results = batch.questions.map((question) => ({
    question_view_id: question.id,
    question_id: question.question_id,
    selected_option: question.selected_option!,
    correct_option: question.correct_option!,
    correct: question.correct!,
  }))
  const score = batch.score ?? results.filter((result) => result.correct).length
  return { score, total: results.length, accuracy: batch.accuracy ?? (results.length ? Math.round(score / results.length * 1000) / 10 : 0), results }
}

export function QuizPage() {
  const [session, setSession] = useState<QuizSession | null>(null)
  const [answers, setAnswers] = useState<Record<number, OptionLabel>>({})
  const [results, setResults] = useState<Record<number, BatchResult>>({})
  const [allowRepeats, setAllowRepeats] = useState(false)
  const [mode, setMode] = useState<SelectionMode>('unseen')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const next = await api.get<QuizSession>('/api/quiz/today')
      const restoredAnswers: Record<number, OptionLabel> = {}
      const restoredResults: Record<number, BatchResult> = {}
      next.batches.forEach((batch) => {
        if (batch.submitted) {
          batch.questions.forEach((question) => { if (question.selected_option) restoredAnswers[question.id] = question.selected_option })
          const result = savedResult(batch)
          if (result) restoredResults[batch.id] = result
        } else {
          Object.assign(restoredAnswers, readDraft(next.id, batch))
        }
      })
      setAnswers(restoredAnswers)
      setResults(restoredResults)
      setSession(next)
    }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not load your study session') }
  }, [])
  useEffect(() => { void load() }, [load])
  useEffect(() => {
    if (!session) return
    session.batches.filter((batch) => !batch.submitted).forEach((batch) => {
      const draft = Object.fromEntries(batch.questions.flatMap((question) => answers[question.id] ? [[question.id, answers[question.id]]] : []))
      if (Object.keys(draft).length) localStorage.setItem(draftKey(session.id, batch.id), JSON.stringify(draft))
      else localStorage.removeItem(draftKey(session.id, batch.id))
    })
  }, [answers, session])

  const active = useMemo(() => session?.batches.find((batch) => !batch.submitted) ?? null, [session])
  const submit = async (batch: Batch) => {
    if (batch.questions.some((question) => !answers[question.id])) return
    setBusy(true)
    try {
      const result = await api.post<BatchResult>(`/api/quiz/batches/${batch.id}/submit`, { answers: batch.questions.map((q) => ({ question_view_id: q.id, selected_option: answers[q.id] })) })
      setResults((current) => ({ ...current, [batch.id]: result }))
      if (session) localStorage.removeItem(draftKey(session.id, batch.id))
      const byView = new Map(result.results.map((answer) => [answer.question_view_id, answer]))
      setSession((current) => current ? { ...current, batches: current.batches.map((item) => item.id === batch.id ? { ...item, submitted: true, score: result.score, accuracy: result.accuracy, questions: item.questions.map((question) => { const answer = byView.get(question.id); return answer ? { ...question, selected_option: answer.selected_option, correct_option: answer.correct_option, correct: answer.correct } : question }) } : item) } : current)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not submit answers') }
    finally { setBusy(false) }
  }
  const nextBatch = async () => {
    setBusy(true)
    try {
      const batch = await api.post<Batch>('/api/quiz/batches', { allow_repeats: allowRepeats, mode })
      setSession((current) => current ? { ...current, batches: [...current.batches, batch] } : current)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create a new batch') }
    finally { setBusy(false) }
  }
  const classify = async (viewId: number, mistakeType: MistakeType) => {
    await api.patch<void>(`/api/quiz/views/${viewId}/mistake`, { mistake_type: mistakeType })
    setSession((current) => current ? { ...current, batches: current.batches.map((batch) => ({ ...batch, questions: batch.questions.map((question) => question.id === viewId ? { ...question, mistake_type: mistakeType } : question) })) } : current)
  }

  if (!session && !error) return <Loading />
  if (!session) return <ErrorState message={error!} retry={() => void load()} />
  if (session.bank_empty) return <section className="mx-auto max-w-3xl px-5 py-20 text-center"><div className="card p-10 sm:p-14"><span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-sage-100 text-sage-700"><CircleAlert/></span><h1 className="mt-6 font-serif text-3xl">Your question bank is empty</h1><p className="mx-auto mt-3 max-w-lg text-black/55">Sync the official online Reálie database in Admin. RealiePrep validates the complete bank before adding any questions.</p><Link className="btn-primary mt-7" to="/admin">Open Admin <ArrowRight size={18}/></Link></div></section>

  const visibleBatch = active ?? session.batches.at(-1)
  const result = visibleBatch ? results[visibleBatch.id] : undefined
  return <section className="mx-auto max-w-4xl px-5 py-10 lg:py-14">
    <div className="mb-9 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
      <div><p className="eyebrow">Today’s session</p><h1 className="mt-2 font-serif text-4xl font-bold tracking-tight sm:text-5xl">Ten questions.<br/><span className="text-sage-600">One step closer.</span></h1></div>
      <div className="rounded-xl bg-white px-4 py-3 text-sm shadow-sm"><span className="text-black/45">Completed today</span><strong className="ml-2 text-sage-700">{session.batches.filter((b) => b.submitted).length} batches</strong></div>
    </div>
    {error && <div className="mb-5 rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
    {visibleBatch && <div>
      <div className="mb-4 flex items-center justify-between"><h2 className="font-serif text-2xl">Batch {visibleBatch.batch_number}</h2><span className="text-sm text-black/45">{visibleBatch.questions.length} questions</span></div>
      <div className="space-y-5">{visibleBatch.questions.map((question, index) => {
        const answerResult = result?.results.find((item) => item.question_view_id === question.id)
        return <article key={question.id} className={`card overflow-hidden p-5 sm:p-7 ${answerResult ? answerResult.correct ? 'ring-2 ring-sage-500/30' : 'ring-2 ring-red-400/25' : ''}`}>
          <div className="flex gap-4"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-sage-50 text-sm font-bold text-sage-700">{index + 1}</span><div className="min-w-0 flex-1"><p className="text-xs font-semibold uppercase tracking-wider text-black/40">{question.category}</p><h3 className="mt-2 text-lg font-semibold leading-relaxed">{question.text}</h3>{question.image_path && <img className="mt-4 max-h-72 rounded-xl border object-contain" src={question.image_path} alt="Question reference"/>}</div></div>
          <div className="mt-5 grid gap-2 sm:grid-cols-2">{question.options.map((option) => {
            const selected = answers[question.id] === option.label
            const correctAfter = answerResult?.correct_option === option.label
            const wrongSelected = Boolean(answerResult && selected && !answerResult.correct)
            return <button key={option.label} disabled={Boolean(answerResult)} onClick={() => setAnswers((current) => ({ ...current, [question.id]: option.label }))} className={`flex min-h-14 items-center gap-3 rounded-xl border p-3 text-left transition ${correctAfter ? 'border-sage-500 bg-sage-50' : wrongSelected ? 'border-red-300 bg-red-50' : selected ? 'border-sage-600 bg-sage-50' : 'border-black/10 bg-white hover:border-sage-500/50'}`}>
              <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg text-sm font-bold ${selected || correctAfter ? 'bg-sage-700 text-white' : 'bg-black/5 text-black/55'}`}>{correctAfter ? <Check size={16}/> : option.label}</span>
              <span className="flex-1"><span className={option.image_path ? 'sr-only' : ''}>{option.text}</span>{option.image_path && <img className="max-h-36 w-full rounded-lg object-contain" src={option.image_path} alt={`Option ${option.label}`}/>}</span>
            </button>
          })}</div>
          {answerResult && !answerResult.correct && <div className="mt-5 rounded-xl bg-red-50/70 p-4"><p className="text-sm font-semibold text-red-800">Your answer: {answerResult.selected_option} · Correct: {answerResult.correct_option}</p><p className="mt-3 text-xs font-semibold uppercase tracking-wide text-black/45">Why did you miss this?</p><div className="mt-2 flex flex-wrap gap-2">{(Object.keys(mistakeLabels) as MistakeType[]).map((kind) => <button key={kind} className={`rounded-lg border px-3 py-2 text-xs font-semibold hover:border-sage-500 ${question.mistake_type === kind ? 'border-sage-500 bg-sage-50' : 'border-black/10 bg-white'}`} onClick={() => void classify(question.id, kind)}>{mistakeLabels[kind]}</button>)}</div></div>}
        </article>
      })}</div>
      {!visibleBatch.submitted ? <div className="sticky bottom-4 mt-6 rounded-2xl border border-white/60 bg-white/90 p-4 shadow-card backdrop-blur"><button className="btn-primary w-full" disabled={busy || visibleBatch.questions.some((q) => !answers[q.id])} onClick={() => void submit(visibleBatch)}>{busy ? 'Checking…' : `Submit answers (${visibleBatch.questions.filter((q) => answers[q.id]).length}/${visibleBatch.questions.length})`}<ArrowRight size={18}/></button></div>
      : <div className="card mt-7 p-6 sm:p-8"><div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center"><div><p className="eyebrow">Batch complete</p><p className="mt-2 font-serif text-4xl">{result ? `${result.score} / ${result.total}` : 'Saved'}</p>{result && <p className="mt-1 text-black/50">{result.accuracy}% accuracy</p>}</div><Sparkles className="text-amber-500" size={42}/></div><div className="mt-7 grid gap-3 sm:grid-cols-2"><label className="flex items-center gap-3 rounded-xl border border-black/10 p-3 text-sm"><input type="checkbox" checked={allowRepeats} onChange={(e) => setAllowRepeats(e.target.checked)} className="h-4 w-4 accent-sage-700"/>Allow previously shown questions</label><select className="rounded-xl border border-black/10 bg-white p-3 text-sm" value={mode} onChange={(e) => setMode(e.target.value as SelectionMode)}><option value="unseen">Unseen first</option><option value="mixed">Mixed review</option><option value="weak_topics">Weak topics</option><option value="incorrect">Previously incorrect</option><option value="missed_twice">Missed twice</option></select></div><button className="btn-primary mt-4 w-full" disabled={busy} onClick={() => void nextBatch()}><RotateCcw size={17}/>Show 10 more</button></div>}
    </div>}
  </section>
}
