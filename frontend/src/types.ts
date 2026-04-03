export type ChatRole = "user" | "assistant" | "system";

export interface QuoteResult {
  product_type?: string;
  premium?: number;
  annual_premium?: number;
  currency?: string;
  summary?: string;
  coverage_level?: string;
  term_years?: string | number;
  [key: string]: unknown;
}

export interface SessionSnapshot {
  session_id?: string;
  mode?: string;
  intent?: string;
  quote_step?: string;
  insurance_type?: string | null;
  current_field?: string | null;
  trace_id?: string | null;
  has_quote_result?: boolean;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  streaming?: boolean;
  quoteResult?: QuoteResult | null;
  kind?: "normal" | "error" | "info";
}

export interface SavedChatSession {
  sessionId: string;
  label: string;
  preview: string;
  updatedAt: string;
  messages: ChatMessage[];
  sessionSnapshot: SessionSnapshot | null;
  quoteResult: QuoteResult | null;
}

export interface SseEvent {
  event: string;
  data: string;
}
