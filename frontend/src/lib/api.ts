// ── OrbitalAuto · API Client ────────────────────────────────────
/**
 * Wrapper centralizado para todas as chamadas ao backend FastAPI.
 * Gerencia token de autenticação e tratamento de erros.
 */

import type {
  LoginRequest,
  LoginResponse,
  StatusResponse,
  CardapioResponse,
  AgendamentosResponse,
  AgendarRequest,
  AgendarSelecionadoItem,
  AgendarSemanaResponse,
  MessageResponse,
  MealCode,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// ── Token Management ────────────────────────────────────────────

const TOKEN_KEY = "orbital_token";
const USER_KEY = "orbital_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUserName(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(USER_KEY);
}

export function setUserName(name: string): void {
  localStorage.setItem(USER_KEY, name);
}

// ── Base Fetch ──────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = `${API_URL}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch {
    throw new ApiError(
      "Não foi possível conectar ao servidor. Tente novamente.",
      0
    );
  }

  // Erro HTTP → ler corpo e lançar
  if (!response.ok) {
    let detail = "Erro desconhecido";
    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch {
      // Resposta não é JSON
    }

    // Se 401 em endpoint de auth, limpar token e redirecionar
    if (response.status === 401) {
      // Só redirecionar se o 401 veio de endpoint de auth (não de dados)
      const isAuthEndpoint = path.includes("/auth/");
      if (isAuthEndpoint) {
        removeToken();
        if (
          typeof window !== "undefined" &&
          !window.location.pathname.includes("/login")
        ) {
          window.location.href = "/login";
        }
      }
    }

    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

// ── Auth Endpoints ──────────────────────────────────────────────

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const result = await apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });

  setToken(result.token);
  setUserName(result.nome);

  return result;
}

export async function logout(): Promise<void> {
  try {
    await apiFetch<MessageResponse>("/api/auth/logout", {
      method: "POST",
    });
  } catch {
    // Mesmo se falhar, limpar localmente
  }
  removeToken();
}

export async function checkAuth(): Promise<StatusResponse> {
  return apiFetch<StatusResponse>("/api/auth/status");
}

// ── Cardápio ────────────────────────────────────────────────────

export async function getCardapio(): Promise<CardapioResponse> {
  return apiFetch<CardapioResponse>("/api/cardapio");
}

// ── Agendamentos ────────────────────────────────────────────────

export async function getAgendamentos(): Promise<AgendamentosResponse> {
  return apiFetch<AgendamentosResponse>("/api/agendamentos");
}

export async function agendar(data: AgendarRequest): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/api/agendar", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function agendarSemana(
  refeicoes: MealCode[] = ["LM", "AL", "LT", "JA"]
): Promise<AgendarSemanaResponse> {
  return apiFetch<AgendarSemanaResponse>("/api/agendar-semana", {
    method: "POST",
    body: JSON.stringify({ refeicoes }),
  });
}

export async function agendarSelecionados(
  items: AgendarSelecionadoItem[]
): Promise<AgendarSemanaResponse> {
  return apiFetch<AgendarSemanaResponse>("/api/agendar-selecionados", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

export async function desagendar(
  agendamentoId: number,
  dia?: string
): Promise<MessageResponse> {
  const params = dia ? `?dia=${dia}` : "";
  return apiFetch<MessageResponse>(`/api/agendar/${agendamentoId}${params}`, {
    method: "DELETE",
  });
}
