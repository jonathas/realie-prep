import { AlertCircle, LoaderCircle } from 'lucide-react'

export function Loading() { return <div className="grid min-h-[55vh] place-items-center"><LoaderCircle className="animate-spin text-sage-600" size={34}/></div> }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { return <div className="card mx-auto mt-16 max-w-lg p-8 text-center"><AlertCircle className="mx-auto text-amber-500" size={36}/><h2 className="mt-4 font-serif text-2xl">We hit a snag</h2><p className="mt-2 text-black/60">{message}</p>{retry && <button className="btn-secondary mt-6" onClick={retry}>Try again</button>}</div> }

