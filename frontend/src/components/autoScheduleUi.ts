import type {
  Agendamento,
  AutoScheduleConfigRequest,
  AutoScheduleConfigResponse,
  AutoScheduleDurationMode,
  AutoScheduleStatusResponse,
  DiaCardapio,
  MealCode,
  WeeklyRules,
  WeekdayCode,
} from "@/types";
import { MEALS, WEEKDAY_ORDER } from "@/types";

export const AUTOMATION_EDITABLE_WEEKDAYS: WeekdayCode[] = [
  "MON",
  "TUE",
  "WED",
  "THU",
  "FRI",
];

export const DURATION_OPTIONS: Array<{
  value: AutoScheduleDurationMode;
  label: string;
}> = [
  { value: "30d", label: "30 dias" },
  { value: "90d", label: "90 dias" },
  { value: "end_of_year", label: "Fim do ano" },
];

export const WEEKDAY_META: Record<
  WeekdayCode,
  { short: string; full: string; compact: string }
> = {
  MON: { short: "Seg", full: "Segunda-feira", compact: "segunda" },
  TUE: { short: "Ter", full: "Terça-feira", compact: "terca" },
  WED: { short: "Qua", full: "Quarta-feira", compact: "quarta" },
  THU: { short: "Qui", full: "Quinta-feira", compact: "quinta" },
  FRI: { short: "Sex", full: "Sexta-feira", compact: "sexta" },
  SAT: { short: "Sab", full: "Sábado", compact: "sabado" },
  SUN: { short: "Dom", full: "Domingo", compact: "domingo" },
};

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
});

const DATE_FORMATTER = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
});

export function emptyWeeklyRules(): WeeklyRules {
  return {
    MON: [],
    TUE: [],
    WED: [],
    THU: [],
    FRI: [],
    SAT: [],
    SUN: [],
  };
}

export function normalizeWeeklyRules(value?: Partial<Record<WeekdayCode, MealCode[]>> | null): WeeklyRules {
  const normalized = emptyWeeklyRules();

  for (const weekday of WEEKDAY_ORDER) {
    const meals = value?.[weekday] ?? [];
    normalized[weekday] = Array.from(
      new Set(meals.filter((meal): meal is MealCode => Boolean(meal)))
    );
  }

  return normalized;
}

export function sanitizeAutomationWeeklyRules(
  value?: Partial<Record<WeekdayCode, MealCode[]>> | null
): WeeklyRules {
  const normalized = normalizeWeeklyRules(value);
  normalized.SAT = [];
  normalized.SUN = [];
  return normalized;
}

export function emptyDraft(): AutoScheduleConfigResponse {
  return {
    enabled: false,
    weekly_rules: emptyWeeklyRules(),
    duration_mode: "30d",
    active_until: null,
    updated_at: null,
    last_successful_run_at: null,
    has_credentials: false,
    credentials_updated_at: null,
    primary_day: "SAT",
    primary_run_time: null,
    fallback_day: "SUN",
    fallback_run_time: null,
  };
}

export function cloneDraft(value: AutoScheduleConfigResponse): AutoScheduleConfigResponse {
  return {
    ...value,
    weekly_rules: sanitizeAutomationWeeklyRules(value.weekly_rules),
  };
}

export function buildRequest(
  draft: AutoScheduleConfigResponse,
  orbitalPassword?: string,
  clearSavedCredentials = false
): AutoScheduleConfigRequest {
  const normalizedPassword = orbitalPassword?.trim() || undefined;
  return {
    enabled: draft.enabled,
    weekly_rules: sanitizeAutomationWeeklyRules(draft.weekly_rules),
    duration_mode: draft.duration_mode,
    orbital_password: normalizedPassword,
    clear_saved_credentials: clearSavedCredentials,
  };
}

export function formatDateTime(value?: string | null): string {
  if (!value) {
    return "Nao disponivel";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return DATE_TIME_FORMATTER.format(parsed);
}

export function formatDate(value?: string | null): string {
  if (!value) {
    return "Nao definido";
  }

  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return DATE_FORMATTER.format(parsed);
}

export function isExpired(activeUntil?: string | null): boolean {
  if (!activeUntil) {
    return false;
  }

  const limit = new Date(`${activeUntil}T23:59:59`);
  return !Number.isNaN(limit.getTime()) && limit.getTime() < Date.now();
}

export function getAutomationState(status: AutoScheduleStatusResponse | null) {
  const expired = isExpired(status?.active_until);
  const active = Boolean(status?.enabled) && !expired;

  return {
    active,
    expired,
    label: active ? "Ativa" : expired ? "Expirada" : "Inativa",
  };
}

export function formatWeekendSlot(day: "SAT" | "SUN", runTime?: string | null): string {
  const label = day === "SAT" ? "Sabado" : "Domingo";
  if (!runTime) {
    return `${label}: horario ainda nao definido`;
  }
  return `${label} as ${runTime}`;
}

export function shortDay(diaSemana: string): string {
  const normalized = diaSemana.normalize("NFD").replace(/\p{Diacritic}/gu, "");
  const map: Record<string, string> = {
    "Segunda-feira": "Seg",
    "Terca-feira": "Ter",
    "Quarta-feira": "Qua",
    "Quinta-feira": "Qui",
    "Sexta-feira": "Sex",
    Sabado: "Sab",
    Domingo: "Dom",
  };

  return map[normalized] || diaSemana.slice(0, 3);
}

export function isMealAvailable(dia: DiaCardapio, code: MealCode): boolean {
  return dia.refeicoes.some((refeicao) => refeicao.tipo === code);
}

export function isAlreadyScheduled(
  dia: string,
  code: MealCode,
  agendamentos: Agendamento[]
): boolean {
  return agendamentos.some((item) => item.dia === dia && item.tipo_codigo === code);
}

export function weekdayCodeFromDate(dateStr: string): WeekdayCode {
  const parsed = new Date(`${dateStr}T12:00:00`);
  const day = parsed.getDay();

  switch (day) {
    case 0:
      return "SUN";
    case 1:
      return "MON";
    case 2:
      return "TUE";
    case 3:
      return "WED";
    case 4:
      return "THU";
    case 5:
      return "FRI";
    default:
      return "SAT";
  }
}

export function hasAnyWeeklyRule(weeklyRules: WeeklyRules): boolean {
  return AUTOMATION_EDITABLE_WEEKDAYS.some(
    (weekday) => (weeklyRules[weekday] ?? []).length > 0
  );
}

export function toggleWeeklyRule(
  weeklyRules: WeeklyRules,
  weekday: WeekdayCode,
  meal: MealCode
): WeeklyRules {
  const next = sanitizeAutomationWeeklyRules(weeklyRules);
  const current = next[weekday];
  next[weekday] = current.includes(meal)
    ? current.filter((value) => value !== meal)
    : [...current, meal];
  return next;
}

function joinLabels(labels: string[]): string {
  if (labels.length === 0) {
    return "";
  }

  if (labels.length === 1) {
    return labels[0];
  }

  if (labels.length === 2) {
    return `${labels[0]} e ${labels[1]}`;
  }

  return `${labels.slice(0, -1).join(", ")} e ${labels[labels.length - 1]}`;
}

function mealNames(meals: MealCode[]): string[] {
  return MEALS.filter((meal) => meals.includes(meal.code)).map((meal) => meal.nome);
}

function weekdayCompactNames(days: WeekdayCode[]): string[] {
  return days.map((day) => WEEKDAY_META[day].short);
}

export function summarizeSelectedMeals(meals: MealCode[]): string {
  return joinLabels(mealNames(meals)) || "nenhuma refeicao";
}

export function summarizeWeeklyRules(weeklyRules: WeeklyRules): string {
  const groups = new Map<string, { days: WeekdayCode[]; meals: MealCode[] }>();

  for (const weekday of AUTOMATION_EDITABLE_WEEKDAYS) {
    const meals = weeklyRules[weekday] ?? [];
    if (meals.length === 0) {
      continue;
    }

    const key = meals.join("|");
    const current = groups.get(key);
    if (current) {
      current.days.push(weekday);
      continue;
    }

    groups.set(key, {
      days: [weekday],
      meals,
    });
  }

  const fragments = Array.from(groups.values()).map((group) => {
    const dayLabel = joinLabels(weekdayCompactNames(group.days));
    const mealLabel = summarizeSelectedMeals(group.meals);
    return `${dayLabel}: ${mealLabel}`;
  });

  return fragments.join("; ");
}

export function selectionSummary(enabled: boolean, weeklyRules: WeeklyRules): string {
  if (!enabled) {
    return "Automacao desativada";
  }

  if (!hasAnyWeeklyRule(weeklyRules)) {
    return "Selecione ao menos uma combinacao de dia e refeicao";
  }

  return summarizeWeeklyRules(weeklyRules);
}
