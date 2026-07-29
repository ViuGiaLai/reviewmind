export interface Issue {
  id: string;
  severity: "high" | "medium" | "low";
  category: string;
  message: string;
  recommendation: string;
  confidence: number;
  evidence_excerpt?: string;
  evidence_location?: string;
  evidence_line_start?: number;
  evidence_line_end?: number;
  rule_id: string;
  source: string;
  status: string;
  autofix_allowed: number;
  scan_history?: { status: string; created_at: string }[];
}

export interface HistoryItem {
  id: string;
  score: number;
  status: string;
  profile_id: string;
  filename: string;
  created_at: string;
  summary?: string;
}

export interface SessionDetail {
  id: string;
  filename: string;
  profile_id: string;
  pack_ids?: string[];
  score: number;
  status: string;
  created_at: string;
  category_scores: Record<string, number>;
  issues: Issue[];
  summary?: string;
  report_markdown?: string;
  duration_ms?: number;
  doc_stats?: { pages: number; paragraphs: number; headings: number; tables: number; figures: number; words: number; references: number; chars: number };
  rule_stats?: { loaded: number; passed: number; failed: number; skipped: number; execution_ms: number };
  pipeline_status?: Record<string, { status: string; label: string }>;
  detected_profile?: string;
  document_id?: string;
}

export type Page = "landing" | "home" | "reviews" | "review-new" | "review-detail" | "documents" | "templates" | "history" | "profiles" | "kbpacks" | "ai" | "settings";
export interface SidebarSection { label: string; items: { id: Page; label: string; Icon: any }[] }
export interface DocumentItem { id: string; name: string; uploaded_at: string }
export interface DashboardStats { total_reviews: number; average_score: number; total_issues: number; open_issues: number; resolved_issues: number; issues_by_severity: Record<string, number>; recent_reviews: HistoryItem[] }
export interface KnowledgePackItem { id: string; name: string; description: string; profile: string; version?: string; categories?: string[]; required_packs?: string[]; incompatible_packs?: string[]; capability_count?: number }
export interface ReferenceTemplateItem {
  id: string; original_name: string; size: number; created_at: string;
  analysis: { body?: { font_name?: string; font_size?: number; line_spacing?: number }; layout?: Record<string, number>; required_sections?: string[]; content_policy?: string; body_text_is_user_owned?: boolean };
}
export type ApiFetch = (url: string, options?: RequestInit) => Promise<Response>;
export interface AccountInfo { name: string; email: string; role: string }
export interface EvaluationProfile {
  id: string;
  name: string;
  description: string;
  base_profile_id: string;
  document_types: string[];
  knowledge_pack_ids: string[];
  reference_template_id: string | null;
  template_name?: string | null;
  enabled_categories: string[];
  ai_review_enabled: boolean;
  auto_fix_enabled: boolean;
  scoring_profile: "weighted" | "equal";
  language: "vi" | "en";
  review_mode: "strict" | "standard" | "relaxed";
  visibility: "private";
  created_at?: string;
  updated_at?: string;
}