"use client";

import { Check } from "lucide-react";
import type { AutoScheduleDurationMode, MealCode, WeeklyRules, WeekdayCode } from "@/types";
import { MEALS } from "@/types";
import {
  AUTOMATION_EDITABLE_WEEKDAYS,
  DURATION_OPTIONS,
  summarizeWeeklyRules,
  WEEKDAY_META,
} from "./autoScheduleUi";

interface AutoScheduleMealSelectorProps {
  weeklyRules: WeeklyRules;
  durationMode: AutoScheduleDurationMode;
  onToggleMeal: (weekday: WeekdayCode, code: MealCode) => void;
  onSelectDuration: (value: AutoScheduleDurationMode) => void;
}

export default function AutoScheduleMealSelector({
  weeklyRules,
  durationMode,
  onToggleMeal,
  onSelectDuration,
}: AutoScheduleMealSelectorProps) {
  const summary = summarizeWeeklyRules(weeklyRules);

  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">Template semanal</h3>
        <p className="text-sm text-slate-500">
          Escolha exatamente quais refeicoes entram em cada dia util. Cada celula funciona de forma independente.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <div className="grid grid-cols-[120px_repeat(4,_minmax(0,1fr))] gap-3 border-b border-slate-200 pb-3">
              <div className="flex items-center text-xs font-semibold uppercase tracking-wide text-slate-400">
                Dias
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

            <div className="mt-3 divide-y divide-slate-100">
              {AUTOMATION_EDITABLE_WEEKDAYS.map((weekday) => (
                <div
                  key={weekday}
                  className="grid grid-cols-[120px_repeat(4,_minmax(0,1fr))] gap-3 py-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900">
                      {WEEKDAY_META[weekday].short}
                    </p>
                    <p className="text-xs text-slate-500">{WEEKDAY_META[weekday].full}</p>
                  </div>

                  {MEALS.map((meal) => {
                    const selected = weeklyRules[weekday]?.includes(meal.code) ?? false;

                    return (
                      <button
                        key={`${weekday}-${meal.code}`}
                        type="button"
                        onClick={() => onToggleMeal(weekday, meal.code)}
                        className={`flex h-12 items-center justify-center rounded-xl border transition-all ${
                          selected
                            ? `${meal.borderColor} ${meal.bgColor} ${meal.color} ring-2 ring-[#006633]/10`
                            : "border-slate-200 bg-white text-slate-300 hover:border-slate-300 hover:bg-slate-50"
                        }`}
                        title={
                          selected
                            ? `${WEEKDAY_META[weekday].full}: ${meal.nome} selecionado`
                            : `${WEEKDAY_META[weekday].full}: adicionar ${meal.nome}`
                        }
                      >
                        {selected ? <Check className="h-4 w-4" /> : <span className="h-2 w-2 rounded-full bg-current" />}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-2xl bg-slate-50 px-4 py-3">
          <p className="text-sm font-semibold text-slate-900">Resumo da regra</p>
          <p className="mt-1 text-sm text-slate-500">
            {summary || "Nenhuma combinacao de dia e refeicao foi selecionada ainda."}
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h4 className="text-sm font-semibold text-slate-900">Validade</h4>
            <p className="mt-1 text-sm text-slate-500">
              Define ate quando a automacao continua valendo sem precisar renovar.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-2 sm:min-w-[280px]">
            {DURATION_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onSelectDuration(option.value)}
                className={`rounded-xl px-3 py-2 text-sm font-semibold transition-colors ${
                  durationMode === option.value
                    ? "bg-[#006633] text-white"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
