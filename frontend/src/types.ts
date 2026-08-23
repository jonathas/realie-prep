export type OptionLabel = 'A' | 'B' | 'C' | 'D'
export type MistakeType = 'vocabulary' | 'knowledge' | 'careless' | 'unknown'
export type SelectionMode = 'unseen' | 'mixed' | 'weak_topics' | 'incorrect' | 'missed_twice'

export interface QuestionOption { label: OptionLabel; text: string; image_path: string | null }
export interface Question { id: number; stable_key: string; category: string; text: string; image_path: string | null; options: QuestionOption[] }
export interface Batch { id: number; batch_number: number; submitted: boolean; allow_repeats: boolean; selection_mode: SelectionMode; questions: Question[] }
export interface QuizSession { id: number; date: string; batches: Batch[]; bank_empty: boolean }
export interface AnswerResult { question_view_id: number; question_id: number; selected_option: OptionLabel; correct_option: OptionLabel; correct: boolean }
export interface BatchResult { score: number; total: number; accuracy: number; results: AnswerResult[] }
export interface CategoryStat { category: string; questions_attempted: number; attempts: number; correct: number; incorrect: number; overall_accuracy: number; first_accuracy: number }
export interface MissedQuestion { question_id: number; question: string; category: string; incorrect_attempts: number; last_attempt: string }
export interface Stats { total_questions: number; unique_seen: number; unique_remaining: number; coverage_percent: number; total_attempts: number; correct: number; incorrect: number; overall_accuracy: number; first_attempt_accuracy: number; passing_grade_percent: number; passing_difference: number; mistakes: Record<MistakeType, number>; categories: CategoryStat[]; weakest_categories: CategoryStat[]; strongest_categories: CategoryStat[]; missed_twice: MissedQuestion[] }
export interface AdminStatus { database_status: string; filename: string | null; source_url: string | null; sha256: string | null; imported_at: string | null; validation_status: string | null; question_count: number; category_count: number; option_count: number }
export interface ImportPreview { token: string; filename: string; sha256: string; question_count: number; category_count: number; option_count: number; valid: boolean; errors: string[] }
