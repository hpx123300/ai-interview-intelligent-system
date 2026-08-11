export interface RubricItem {
  criterion: string;
  weight: number;
  description: string;
}

export interface Question {
  id: string;
  question: string;
  topic: string;
  level: string;
  hint: string;
  difficulty: number;
  competency: string;
  rubric: RubricItem[];
  followups: string[];
}

export interface ProfileProject {
  name: string;
  tech_stack: string;
  description: string;
  metrics: string;
  story: string;
}

export interface JdAnalysis {
  title?: string;
  company_name?: string;
  seniority?: string;
  must_have?: string[];
  nice_to_have?: string[];
  responsibilities?: string[];
  tech_stack?: string[];
  raw_text?: string;
  gap?: {
    strengths: string[];
    gaps: string[];
    probe_targets: string[];
    matched_skills: string[];
    missing_skills: string[];
    summary: string;
  };
}

export interface Profile {
  profile_key: string;
  target_role: string;
  target_direction: string;
  skills: string[];
  weak_areas: string[];
  projects: ProfileProject[];
  jd_text: string;
  jd_analysis: JdAnalysis;
  resume_text: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface TraceStep {
  step: string;
  content: string;
}

export interface ToolCard {
  type: "knowledge" | "questions" | "jobs";
  items?: unknown[];
  text?: string;
}

export interface AnswerFeedback {
  feedback: string;
  followup: string;
  score: number;
  score_evidence: string;
  score_hint: string;
}

export interface CompetencyScore {
  competency: string;
  score: number;
  evidence: string;
  level: "strong" | "solid" | "developing" | "weak";
}

export interface LanguageReport {
  structure_score?: number;
  clarity_score?: number;
  conciseness_score?: number;
  summary?: string;
}

export interface CoachModule {
  title: string;
  competency: string;
  est_min: number;
  rationale: string;
  focus_points: string[];
  sources: string[];
}

export interface CoachPlan {
  summary: string;
  modules: CoachModule[];
  total_min: number;
}

export interface ModelAnswer {
  question: string;
  answer: string;
}

export interface Report {
  total_score: number;
  dimensions: Record<string, number>;
  highlights: string[];
  weaknesses: string[];
  missing_points: string[];
  suggestions: string[];
  summary: string;
  next_steps: string[];
  language_report: LanguageReport;
  competency_scores: CompetencyScore[];
  weak_competencies: string[];
  model_answers: ModelAnswer[];
  coverage_pct: number;
  coach_plan?: CoachPlan;
}

export interface Comparison {
  history_count: number;
  history_avg?: Record<string, number>;
  progress: string[];
  regress: string[];
  stable: string[];
  priority: string[];
}

export interface InterviewSummary {
  id: string;
  direction: string;
  status: string;
  score: number;
  created_at: string;
  finished_at: string;
}

export interface InterviewDetail {
  interview: InterviewSummary;
  report: Report | null;
  qa_list: Array<{
    id: number;
    question: string;
    topic: string;
    level: string;
    hint: string;
    difficulty: number;
    competency: string;
    rubric: string;
    answer: string;
    answer_score: number;
    feedback: string;
    followup: string;
    followup_answer: string;
    reference: string;
  }>;
}

export interface Review {
  id: number;
  summary: string;
  source_text: string;
  highlights: string[];
  weaknesses: string[];
  key_points: string[];
  action_plan: string[];
  created_at: string;
}

export interface Dashboard {
  total_sessions: number;
  avg_score: number | null;
  max_score: number | null;
  last_score: number | null;
  trend: number[];
  weak_dimensions: Array<{ name: string; score: number }>;
  todos: string[];
  reviews: Review[];
}

export interface DesignQuestion {
  text: string;
  type: string;
  follow_up_prompts: string[];
  time_limit_seconds: number | null;
  is_required: boolean;
}

export interface InterviewDesign {
  title: string;
  description: string;
  objective: string;
  assessment_criteria: Array<{ name: string; description: string }>;
  questions: DesignQuestion[];
  recommended_settings: {
    mode: string;
    follow_up_depth: string;
    ai_tone: string;
  };
}
