// ── OrbitalAuto · TypeScript Types ─────────────────────────────

// ── Auth ────────────────────────────────────────────────────────

export interface LoginRequest {
  cpf: string;
  senha: string;
}

export interface LoginResponse {
  token: string;
  nome: string;
  message: string;
}

export interface StatusResponse {
  authenticated: boolean;
  nome?: string;
  cpf?: string;
}

// ── Cardápio ────────────────────────────────────────────────────

export interface Refeicao {
  tipo: MealCode;
  nome: string;
  descricao?: string;
}

export interface DiaCardapio {
  data: string; // YYYY-MM-DD
  dia_semana: string;
  refeicoes: Refeicao[];
}

export interface CardapioResponse {
  semana: DiaCardapio[];
}

// ── Agendamentos ────────────────────────────────────────────────

export interface Agendamento {
  id: number;
  dia: string; // YYYY-MM-DD
  tipo_refeicao: string;
  tipo_codigo: MealCode;
  confirmado: boolean;
}

export interface AgendamentosResponse {
  agendamentos: Agendamento[];
}

// ── Ações ───────────────────────────────────────────────────────

export interface AgendarRequest {
  dia: string;
  refeicao: MealCode;
}

export interface AgendarSelecionadoItem {
  dia: string;
  refeicao: MealCode;
}

export interface AgendarSemanaResponse {
  agendados: number;
  erros: string[];
  message: string;
}

export interface MessageResponse {
  message: string;
  success: boolean;
}

export type AutoScheduleDurationMode = "30d" | "90d" | "end_of_year";
export type WeekdayCode = "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN";
export type WeeklyRules = Record<WeekdayCode, MealCode[]>;

export interface AutoScheduleRunResponse {
  trigger: string;
  enabled: boolean;
  dry_run: boolean;
  started_at: string;
  finished_at?: string | null;
  success?: boolean | null;
  message: string;
  used_existing_session: boolean;
  login_performed: boolean;
  candidates_count: number;
  scheduled_count: number;
  already_scheduled_count: number;
  skipped_count: number;
  errors: string[];
  last_error?: string | null;
}

export interface AutoScheduleConfigRequest {
  enabled: boolean;
  weekly_rules: WeeklyRules;
  duration_mode: AutoScheduleDurationMode;
  orbital_password?: string | null;
  clear_saved_credentials?: boolean;
}

export interface AutoScheduleConfigResponse {
  enabled: boolean;
  weekly_rules: WeeklyRules;
  duration_mode: AutoScheduleDurationMode;
  active_until?: string | null;
  updated_at?: string | null;
  last_successful_run_at?: string | null;
  has_credentials: boolean;
  credentials_updated_at?: string | null;
  primary_day: "SAT";
  primary_run_time?: string | null;
  fallback_day: "SUN";
  fallback_run_time?: string | null;
}

export interface AutoScheduleStatusResponse {
  enabled: boolean;
  dry_run: boolean;
  running: boolean;
  timezone: string;
  weekly_rules: WeeklyRules;
  duration_mode: AutoScheduleDurationMode;
  active_until?: string | null;
  updated_at?: string | null;
  last_successful_run_at?: string | null;
  primary_day: "SAT";
  primary_run_time?: string | null;
  fallback_day: "SUN";
  fallback_run_time?: string | null;
  has_credentials: boolean;
  credentials_updated_at?: string | null;
  next_run_at?: string | null;
  last_run?: AutoScheduleRunResponse | null;
}

// ── Enums / Constants ───────────────────────────────────────────

export type MealCode = "LM" | "AL" | "LT" | "JA";
export const WEEKDAY_ORDER: WeekdayCode[] = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

export interface MealInfo {
  code: MealCode;
  nome: string;
  icon: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

export const MEALS: MealInfo[] = [
  {
    code: "LM",
    nome: "Lanche da Manhã",
    icon: "Coffee",
    color: "text-amber-700",
    bgColor: "bg-amber-50",
    borderColor: "border-amber-200",
  },
  {
    code: "AL",
    nome: "Almoço",
    icon: "UtensilsCrossed",
    color: "text-orange-700",
    bgColor: "bg-orange-50",
    borderColor: "border-orange-200",
  },
  {
    code: "LT",
    nome: "Lanche da Tarde",
    icon: "Cookie",
    color: "text-purple-700",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200",
  },
  {
    code: "JA",
    nome: "Jantar",
    icon: "Moon",
    color: "text-blue-700",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
  },
];

// ── Status de refeição (UI) ─────────────────────────────────────

export type MealStatus = "available" | "scheduled" | "expired";
