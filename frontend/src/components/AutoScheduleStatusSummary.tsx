"use client";

import { CalendarDays, Clock3, Loader2, TriangleAlert } from "lucide-react";
import type { AutoScheduleConfigResponse, AutoScheduleStatusResponse } from "@/types";
import {
  formatDate,
  formatDateTime,
  formatWeekendSlot,
  getAutomationState,
} from "./autoScheduleUi";

interface AutoScheduleStatusSummaryProps {
  draft: AutoScheduleConfigResponse;
  status: AutoScheduleStatusResponse | null;
  loading: boolean;
  hasUnsavedToggleChange: boolean;
  onToggleEnabled: () => void;
}

function badgeClasses(active: boolean, expired: boolean) {
  if (active) {
    return "bg-emerald-100 text-emerald-700";
  }

  if (expired) {
    return "bg-amber-100 text-amber-700";
  }

  return "bg-slate-200 text-slate-700";
}

export default function AutoScheduleStatusSummary({
  draft,
  status,
  loading,
  hasUnsavedToggleChange,
  onToggleEnabled,
}: AutoScheduleStatusSummaryProps) {
  const automationState = getAutomationState(status);
  const currentStateLabel = loading ? "Carregando..." : automationState.label;
  const hasCredentials = Boolean(status?.has_credentials ?? draft.has_credentials);
  const credentialsUpdatedAt =
    status?.credentials_updated_at || draft.credentials_updated_at;

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Estado da automacao</h3>
          <p className="text-sm text-slate-500">
            Veja se ela esta ligada e quando deve tentar agendar.
          </p>
        </div>

        <span
          className={`inline-flex w-fit items-center rounded-full px-3 py-1 text-xs font-semibold ${badgeClasses(
            automationState.active,
            automationState.expired
          )}`}
        >
          {currentStateLabel}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-900">
                {draft.enabled ? "Ativado" : "Desativado"}
              </p>
              <p className="mt-1 text-sm text-slate-500">
                {draft.enabled
                  ? "A automacao tenta agendar as combinacoes escolhidas de dia e refeicao todo fim de semana."
                  : "Nada sera agendado automaticamente ate voce ativar."}
              </p>
            </div>

            <button
              type="button"
              onClick={onToggleEnabled}
              className={`relative h-7 w-12 rounded-full transition-colors ${
                draft.enabled ? "bg-[#006633]" : "bg-slate-300"
              }`}
              aria-pressed={draft.enabled}
              aria-label={draft.enabled ? "Desativar automacao" : "Ativar automacao"}
            >
              <span
                className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform ${
                  draft.enabled ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          <div className="mt-4 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Tenta no sabado. Se nao der certo, tenta novamente no domingo.
          </div>

          {hasUnsavedToggleChange ? (
            <div className="mt-3 flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-800">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <p>Essa mudanca so passa a valer depois de salvar.</p>
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 text-slate-900">
            <CalendarDays className="h-4 w-4" />
            <p className="text-sm font-semibold">Quando roda</p>
          </div>

          <div className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Tentativa de sabado</span>
              <span className="text-right font-medium text-slate-800">
                {formatWeekendSlot("SAT", status?.primary_run_time || draft.primary_run_time)}
              </span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Nova tentativa</span>
              <span className="text-right font-medium text-slate-800">
                {formatWeekendSlot("SUN", status?.fallback_run_time || draft.fallback_run_time)}
              </span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Proxima execucao</span>
              <span className="text-right font-medium text-slate-800">
                {formatDateTime(status?.next_run_at)}
              </span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Ultima execucao</span>
              <span className="text-right font-medium text-slate-800">
                {formatDateTime(status?.last_run?.finished_at || status?.last_successful_run_at)}
              </span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Validade</span>
              <span className="text-right font-medium text-slate-800">
                {formatDate(status?.active_until || draft.active_until)}
              </span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Senha salva</span>
              <span className="text-right font-medium text-slate-800">
                {hasCredentials ? "Sim" : "Nao"}
              </span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500">Senha atualizada</span>
              <span className="text-right font-medium text-slate-800">
                {formatDateTime(credentialsUpdatedAt)}
              </span>
            </div>
          </div>

          {status?.running ? (
            <div className="mt-4 flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs text-emerald-800">
              <Loader2 className="h-4 w-4 animate-spin" />
              A automacao esta em execucao neste momento.
            </div>
          ) : null}

          {!status?.running && !loading ? (
            <div className="mt-4 flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-600">
              <Clock3 className="h-4 w-4" />
              Os horarios mostrados aqui sao informativos e nao podem ser alterados nesta etapa.
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
