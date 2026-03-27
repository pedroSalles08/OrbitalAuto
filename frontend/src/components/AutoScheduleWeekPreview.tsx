"use client";

import { CalendarDays, Check, Minus } from "lucide-react";
import type { Agendamento, DiaCardapio, WeeklyRules } from "@/types";
import { MEALS } from "@/types";
import {
  formatDate,
  isAlreadyScheduled,
  isMealAvailable,
  shortDay,
  weekdayCodeFromDate,
} from "./autoScheduleUi";

interface AutoScheduleWeekPreviewProps {
  cardapio: DiaCardapio[];
  agendamentos: Agendamento[];
  weeklyRules: WeeklyRules;
  loading: boolean;
  error: string;
}

export default function AutoScheduleWeekPreview({
  cardapio,
  agendamentos,
  weeklyRules,
  loading,
  error,
}: AutoScheduleWeekPreviewProps) {
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Previa no cardapio atual</h3>
          <p className="text-sm text-slate-500">
            Previa com o cardapio publicado agora, cruzando a regra recorrente da semana com os dias que existem no cardapio.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 text-xs text-slate-600">
          <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1">
            <Check className="h-3.5 w-3.5 text-emerald-600" />
            Ja agendado manualmente
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1">
            <span className="h-2.5 w-2.5 rounded-full bg-[#006633]" />
            Faz parte da automacao
          </span>
          <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1">
            <Minus className="h-3.5 w-3.5 text-slate-400" />
            Nao aparece no cardapio
          </span>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        {loading ? (
          <div className="px-4 py-6 text-sm text-slate-500">Carregando cardapio e agendamentos...</div>
        ) : error ? (
          <div className="px-4 py-6 text-sm text-red-600">{error}</div>
        ) : cardapio.length === 0 ? (
          <div className="px-4 py-6 text-sm text-slate-500">
            Nenhum cardapio publicado nesta semana para montar a previa.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[680px]">
              <div className="grid grid-cols-[110px_repeat(4,_minmax(0,1fr))] gap-3 border-b border-slate-200 px-4 py-4">
                <div className="flex items-center text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Semana
                </div>

                {MEALS.map((meal) => (
                  <div
                    key={meal.code}
                    className={`rounded-xl border px-3 py-3 text-center ${meal.borderColor} ${meal.bgColor}`}
                  >
                    <p className={`text-xs font-semibold uppercase tracking-wide ${meal.color}`}>
                      {meal.code}
                    </p>
                    <p className="mt-1 text-xs font-medium text-slate-700">{meal.nome}</p>
                  </div>
                ))}
              </div>

              <div className="divide-y divide-slate-100">
                {cardapio.map((dia) => (
                  <div
                    key={dia.data}
                    className="grid grid-cols-[110px_repeat(4,_minmax(0,1fr))] gap-3 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 text-slate-900">
                        <CalendarDays className="h-4 w-4 text-slate-400" />
                        <span className="text-sm font-semibold">{shortDay(dia.dia_semana)}</span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{formatDate(dia.data)}</p>
                    </div>

                    {MEALS.map((meal) => {
                      const weekday = weekdayCodeFromDate(dia.data);
                      const available = isMealAvailable(dia, meal.code);
                      const manuallyScheduled = isAlreadyScheduled(dia.data, meal.code, agendamentos);
                      const selected = weeklyRules[weekday]?.includes(meal.code) ?? false;

                      if (!available) {
                        return (
                          <div
                            key={meal.code}
                            className="flex h-12 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-300"
                            title="Essa refeicao nao aparece no cardapio atual."
                          >
                            <Minus className="h-4 w-4" />
                          </div>
                        );
                      }

                      if (manuallyScheduled) {
                        return (
                          <div
                            key={meal.code}
                            className="flex h-12 flex-col items-center justify-center rounded-xl border border-emerald-300 bg-emerald-100 text-emerald-700"
                            title="Essa refeicao ja esta agendada manualmente."
                          >
                            <Check className="h-4 w-4" />
                            <span className="hidden text-[10px] font-semibold md:block">Manual</span>
                          </div>
                        );
                      }

                      if (selected) {
                        return (
                          <div
                            key={meal.code}
                            className={`flex h-12 flex-col items-center justify-center rounded-xl border ${meal.borderColor} ${meal.bgColor} ${meal.color}`}
                            title="Essa refeicao faz parte da automacao atual."
                          >
                            <span className="h-2.5 w-2.5 rounded-full bg-current" />
                            <span className="hidden text-[10px] font-semibold md:block">Auto</span>
                          </div>
                        );
                      }

                      return (
                        <div
                          key={meal.code}
                          className="flex h-12 items-center justify-center rounded-xl border border-slate-200 bg-white"
                          title="Disponivel no cardapio, mas fora da automacao."
                        >
                          <span className="h-2 w-2 rounded-full bg-slate-200" />
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
