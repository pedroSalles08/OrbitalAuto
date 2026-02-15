// ── OrbitalAuto · SchedulePickerButton ──────────────────────────
/**
 * Botão que abre um modal com checkboxes para selecionar
 * exatamente quais refeições de quais dias agendar.
 *
 * Atalhos rápidos:
 *  - "Tudo menos Jantar" (LM + AL + LT de todos os dias disponíveis)
 *  - "Selecionar Tudo"
 *  - "Limpar Seleção"
 */

"use client";

import { useState, useCallback, useMemo } from "react";
import {
  CalendarCheck,
  Loader2,
  X,
  Check,
  Coffee,
  UtensilsCrossed,
  Cookie,
  Moon,
  Minus,
} from "lucide-react";
import type {
  DiaCardapio,
  Agendamento,
  MealCode,
  AgendarSelecionadoItem,
} from "@/types";
import { MEALS } from "@/types";

// ── Types ───────────────────────────────────────────────────────

interface SchedulePickerButtonProps {
  cardapio: DiaCardapio[];
  agendamentos: Agendamento[];
  onScheduleSelected: (
    items: AgendarSelecionadoItem[]
  ) => Promise<{ agendados: number; erros: string[] }>;
}

type SelectionMap = Record<string, Set<MealCode>>;

// ── Icon map ────────────────────────────────────────────────────

const ICON_MAP = {
  Coffee,
  UtensilsCrossed,
  Cookie,
  Moon,
} as const;

// ── Helpers ─────────────────────────────────────────────────────

/** Pode agendar? Até 17h do dia anterior. */
function canSchedule(diaStr: string): boolean {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const mealDate = new Date(diaStr + "T00:00:00");

  if (mealDate < today) return false;
  if (mealDate.getTime() === today.getTime()) return false;

  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (mealDate.getTime() === tomorrow.getTime() && now.getHours() >= 17)
    return false;

  return true;
}

/** Verifica se um agendamento já existe para dia+refeição. */
function isAlreadyScheduled(
  diaStr: string,
  code: MealCode,
  agendamentos: Agendamento[]
): boolean {
  return agendamentos.some((a) => a.dia === diaStr && a.tipo_codigo === code);
}

function formatDate(dateStr: string): string {
  const [, month, day] = dateStr.split("-");
  return `${day}/${month}`;
}

function shortDay(diaSemana: string): string {
  const map: Record<string, string> = {
    "Segunda-feira": "Seg",
    "Terça-feira": "Ter",
    "Quarta-feira": "Qua",
    "Quinta-feira": "Qui",
    "Sexta-feira": "Sex",
    Sábado: "Sáb",
    Domingo: "Dom",
  };
  return map[diaSemana] || diaSemana.slice(0, 3);
}

// ── Component ───────────────────────────────────────────────────

export default function SchedulePickerButton({
  cardapio,
  agendamentos,
  onScheduleSelected,
}: SchedulePickerButtonProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selection, setSelection] = useState<SelectionMap>({});

  // ── Derived data ────────────────────────────────────────────

  /** Dias disponíveis para agendar (prazo ainda não expirou). */
  const availableDays = useMemo(
    () => cardapio.filter((dia) => canSchedule(dia.data)),
    [cardapio]
  );

  /** Total de itens selecionados. */
  const selectedCount = useMemo(
    () =>
      Object.values(selection).reduce((sum, set) => sum + set.size, 0),
    [selection]
  );

  /** Converte seleção para lista de items. */
  const selectedItems: AgendarSelecionadoItem[] = useMemo(() => {
    const items: AgendarSelecionadoItem[] = [];
    for (const [dia, meals] of Object.entries(selection)) {
      for (const meal of meals) {
        items.push({ dia, refeicao: meal });
      }
    }
    return items;
  }, [selection]);

  // ── Selection helpers ─────────────────────────────────────────

  const toggleMeal = useCallback(
    (dia: string, code: MealCode) => {
      setSelection((prev) => {
        const next = { ...prev };
        const daySet = new Set(next[dia] || []);
        if (daySet.has(code)) {
          daySet.delete(code);
        } else {
          daySet.add(code);
        }
        if (daySet.size === 0) {
          delete next[dia];
        } else {
          next[dia] = daySet;
        }
        return next;
      });
    },
    []
  );

  const selectPreset = useCallback(
    (codes: MealCode[]) => {
      const next: SelectionMap = {};
      for (const dia of availableDays) {
        const dayMeals = new Set<MealCode>();
        for (const code of codes) {
          // Só selecionar se a refeição existe no cardápio e NÃO está agendada.
          const hasInMenu = dia.refeicoes.some((r) => r.tipo === code);
          const alreadyDone = isAlreadyScheduled(
            dia.data,
            code,
            agendamentos
          );
          if (hasInMenu && !alreadyDone) {
            dayMeals.add(code);
          }
        }
        if (dayMeals.size > 0) next[dia.data] = dayMeals;
      }
      setSelection(next);
    },
    [availableDays, agendamentos]
  );

  const clearSelection = useCallback(() => setSelection({}), []);

  // ── Open modal ────────────────────────────────────────────────

  const handleOpen = useCallback(() => {
    // Pre-select "Tudo menos Jantar" by default.
    const next: SelectionMap = {};
    const codes: MealCode[] = ["LM", "AL", "LT"];
    for (const dia of availableDays) {
      const dayMeals = new Set<MealCode>();
      for (const code of codes) {
        const hasInMenu = dia.refeicoes.some((r) => r.tipo === code);
        const alreadyDone = isAlreadyScheduled(
          dia.data,
          code,
          agendamentos
        );
        if (hasInMenu && !alreadyDone) {
          dayMeals.add(code);
        }
      }
      if (dayMeals.size > 0) next[dia.data] = dayMeals;
    }
    setSelection(next);
    setOpen(true);
  }, [availableDays, agendamentos]);

  // ── Submit ────────────────────────────────────────────────────

  async function handleSubmit() {
    if (selectedItems.length === 0) return;
    setLoading(true);
    try {
      await onScheduleSelected(selectedItems);
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={handleOpen}
        disabled={loading || availableDays.length === 0}
        className="w-full bg-gradient-to-r from-[#006633] to-green-700 hover:from-green-800 
          hover:to-green-900 disabled:from-gray-400 disabled:to-gray-500
          text-white font-semibold py-4 px-6 rounded-2xl shadow-lg hover:shadow-xl
          transition-all duration-200 flex items-center justify-center gap-3
          cursor-pointer disabled:cursor-not-allowed"
      >
        <CalendarCheck className="w-6 h-6" />
        Agendar Semana
      </button>

      {/* Modal overlay */}
      {open && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col animate-scale-in">
            {/* ── Header ─────────────────────────────────────── */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <div>
                <h3 className="text-lg font-bold text-gray-800">
                  Selecionar Refeições
                </h3>
                <p className="text-sm text-gray-500 mt-0.5">
                  Escolha o que deseja agendar para a semana
                </p>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="p-2 hover:bg-gray-100 rounded-xl transition-colors cursor-pointer"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* ── Quick presets ───────────────────────────────── */}
            <div className="px-6 py-3 border-b border-gray-100 flex flex-wrap gap-2">
              <button
                onClick={() => selectPreset(["LM", "AL", "LT"])}
                className="px-3 py-1.5 text-sm font-medium rounded-lg bg-green-100 text-green-800 
                  hover:bg-green-200 transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <Minus className="w-3.5 h-3.5" />
                Tudo menos Jantar
              </button>
              <button
                onClick={() => selectPreset(["LM", "AL", "LT", "JA"])}
                className="px-3 py-1.5 text-sm font-medium rounded-lg bg-blue-100 text-blue-800 
                  hover:bg-blue-200 transition-colors cursor-pointer flex items-center gap-1.5"
              >
                <Check className="w-3.5 h-3.5" />
                Selecionar Tudo
              </button>
              <button
                onClick={clearSelection}
                className="px-3 py-1.5 text-sm font-medium rounded-lg bg-gray-100 text-gray-600 
                  hover:bg-gray-200 transition-colors cursor-pointer"
              >
                Limpar
              </button>
            </div>

            {/* ── Grid ───────────────────────────────────────── */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {/* Column headers */}
              <div className="grid grid-cols-[1fr_repeat(4,_64px)] gap-2 mb-2 sticky top-0 bg-white pb-2">
                <div /> {/* spacer */}
                {MEALS.map((meal) => {
                  const Icon =
                    ICON_MAP[meal.icon as keyof typeof ICON_MAP];
                  return (
                    <div
                      key={meal.code}
                      className="flex flex-col items-center gap-0.5"
                    >
                      <Icon className={`w-4 h-4 ${meal.color}`} />
                      <span className="text-[10px] font-medium text-gray-500 leading-tight text-center">
                        {meal.code}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Rows — one per day */}
              {availableDays.length === 0 ? (
                <p className="text-center text-gray-400 py-8 text-sm">
                  Nenhum dia disponível para agendar.
                </p>
              ) : (
                availableDays.map((dia) => {
                  const dayAgendamentos = agendamentos.filter(
                    (a) => a.dia === dia.data
                  );
                  return (
                    <div
                      key={dia.data}
                      className="grid grid-cols-[1fr_repeat(4,_64px)] gap-2 items-center py-2 border-b border-gray-50 last:border-b-0"
                    >
                      {/* Day label */}
                      <div className="min-w-0">
                        <span className="font-semibold text-gray-800 text-sm">
                          {shortDay(dia.dia_semana)}
                        </span>
                        <span className="text-gray-400 text-xs ml-1.5">
                          {formatDate(dia.data)}
                        </span>
                      </div>

                      {/* Meal checkboxes */}
                      {MEALS.map((meal) => {
                        const hasInMenu = dia.refeicoes.some(
                          (r) => r.tipo === meal.code
                        );
                        const alreadyScheduled = isAlreadyScheduled(
                          dia.data,
                          meal.code,
                          dayAgendamentos
                        );
                        const isSelected =
                          selection[dia.data]?.has(meal.code) ?? false;

                        // Não disponível no cardápio
                        if (!hasInMenu) {
                          return (
                            <div
                              key={meal.code}
                              className="flex items-center justify-center"
                            >
                              <div className="w-8 h-8 rounded-lg bg-gray-50 flex items-center justify-center">
                                <Minus className="w-3.5 h-3.5 text-gray-300" />
                              </div>
                            </div>
                          );
                        }

                        // Já agendado
                        if (alreadyScheduled) {
                          return (
                            <div
                              key={meal.code}
                              className="flex items-center justify-center"
                            >
                              <div className="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center"
                                title="Já agendado"
                              >
                                <Check className="w-4 h-4 text-green-600" />
                              </div>
                            </div>
                          );
                        }

                        // Selecionável
                        return (
                          <div
                            key={meal.code}
                            className="flex items-center justify-center"
                          >
                            <button
                              onClick={() =>
                                toggleMeal(dia.data, meal.code)
                              }
                              className={`w-8 h-8 rounded-lg border-2 flex items-center justify-center
                                transition-all duration-150 cursor-pointer
                                ${
                                  isSelected
                                    ? `${meal.bgColor} ${meal.borderColor} shadow-sm`
                                    : "bg-white border-gray-200 hover:border-gray-300"
                                }`}
                            >
                              {isSelected && (
                                <Check
                                  className={`w-4 h-4 ${meal.color}`}
                                />
                              )}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  );
                })
              )}

              {/* Days with expired deadlines */}
              {cardapio.filter((d) => !canSchedule(d.data)).length > 0 && (
                <div className="mt-4 pt-3 border-t border-gray-100">
                  <p className="text-xs text-gray-400 mb-2">
                    Prazo expirado:
                  </p>
                  {cardapio
                    .filter((d) => !canSchedule(d.data))
                    .map((dia) => (
                      <div
                        key={dia.data}
                        className="flex items-center gap-2 py-1 opacity-50"
                      >
                        <span className="text-xs text-gray-400">
                          {shortDay(dia.dia_semana)} {formatDate(dia.data)}
                        </span>
                        <span className="text-[10px] text-gray-300">
                          — prazo encerrado
                        </span>
                      </div>
                    ))}
                </div>
              )}
            </div>

            {/* ── Footer ─────────────────────────────────────── */}
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between gap-4">
              <span className="text-sm text-gray-500">
                {selectedCount > 0 ? (
                  <>
                    <span className="font-semibold text-gray-800">
                      {selectedCount}
                    </span>{" "}
                    refeição(ões) selecionada(s)
                  </>
                ) : (
                  "Nenhuma seleção"
                )}
              </span>

              <div className="flex gap-3">
                <button
                  onClick={() => setOpen(false)}
                  className="px-5 py-2.5 border border-gray-300 rounded-xl text-gray-700 
                    hover:bg-gray-50 transition-colors font-medium cursor-pointer text-sm"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={loading || selectedCount === 0}
                  className="px-5 py-2.5 bg-[#006633] hover:bg-green-800 disabled:bg-gray-300
                    text-white rounded-xl transition-colors font-medium cursor-pointer
                    disabled:cursor-not-allowed text-sm flex items-center gap-2 min-w-[160px] justify-center"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Agendando...
                    </>
                  ) : (
                    <>
                      <CalendarCheck className="w-4 h-4" />
                      Agendar Selecionados
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
