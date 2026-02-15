// ── OrbitalAuto · DayCard ───────────────────────────────────────
/**
 * Card que exibe o cardápio e botões de agendamento de um dia.
 */

"use client";

import type {
  DiaCardapio,
  Agendamento,
  MealCode,
  MealStatus,
} from "@/types";
import { MEALS } from "@/types";
import MealButton from "./MealButton";
import { CalendarDays } from "lucide-react";

interface DayCardProps {
  dia: DiaCardapio;
  agendamentos: Agendamento[];
  onSchedule: (dia: string, code: MealCode) => Promise<void>;
  onUnschedule: (id: number) => Promise<void>;
}

// ── Helpers ─────────────────────────────────────────────────────

function formatDate(dateStr: string): string {
  const [year, month, day] = dateStr.split("-");
  return `${day}/${month}/${year}`;
}

function getMealStatus(
  diaStr: string,
  code: MealCode,
  agendamentos: Agendamento[]
): { status: MealStatus; agendamentoId?: number; prazoInfo?: string } {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const mealDate = new Date(diaStr + "T00:00:00");

  // Verificar se já está agendado
  const agendamento = agendamentos.find(
    (a) => a.dia === diaStr && a.tipo_codigo === code
  );

  if (agendamento) {
    // Verificar se pode desagendar (até 9h do dia)
    if (mealDate < today) {
      return {
        status: "expired",
        agendamentoId: agendamento.id,
        prazoInfo: "Data já passou",
      };
    }

    if (
      mealDate.getTime() === today.getTime() &&
      now.getHours() >= 9
    ) {
      return {
        status: "expired",
        agendamentoId: agendamento.id,
        prazoInfo: "Prazo de cancelamento expirado (até 9h)",
      };
    }

    return {
      status: "scheduled",
      agendamentoId: agendamento.id,
      prazoInfo: `Desagendar até ${formatDate(diaStr)} 09h`,
    };
  }

  // Não agendado — verificar se pode agendar (até 17h do dia anterior)
  if (mealDate < today) {
    return { status: "expired", prazoInfo: "Data já passou" };
  }

  if (mealDate.getTime() === today.getTime()) {
    return {
      status: "expired",
      prazoInfo: "Prazo expirado (até 17h de ontem)",
    };
  }

  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  if (
    mealDate.getTime() === tomorrow.getTime() &&
    now.getHours() >= 17
  ) {
    return {
      status: "expired",
      prazoInfo: "Prazo expirado (até 17h de hoje)",
    };
  }

  // Calcular prazo
  const prazoDate = new Date(mealDate);
  prazoDate.setDate(prazoDate.getDate() - 1);
  const prazoStr = `${prazoDate.getDate().toString().padStart(2, "0")}/${(prazoDate.getMonth() + 1).toString().padStart(2, "0")}`;

  return {
    status: "available",
    prazoInfo: `Agendar até ${prazoStr} 17h`,
  };
}

function isToday(dateStr: string): boolean {
  const now = new Date();
  const today = `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, "0")}-${now.getDate().toString().padStart(2, "0")}`;
  return dateStr === today;
}

function isTomorrow(dateStr: string): boolean {
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowStr = `${tomorrow.getFullYear()}-${(tomorrow.getMonth() + 1).toString().padStart(2, "0")}-${tomorrow.getDate().toString().padStart(2, "0")}`;
  return dateStr === tomorrowStr;
}

// ── Component ───────────────────────────────────────────────────

export default function DayCard({
  dia,
  agendamentos,
  onSchedule,
  onUnschedule,
}: DayCardProps) {
  const today = isToday(dia.data);
  const tomorrow = isTomorrow(dia.data);

  // Chip de destaque
  const chip = today
    ? { label: "Hoje", color: "bg-blue-100 text-blue-700" }
    : tomorrow
      ? { label: "Amanhã", color: "bg-amber-100 text-amber-700" }
      : null;

  return (
    <div
      className={`bg-white rounded-2xl shadow-sm border overflow-hidden transition-shadow
        hover:shadow-md ${
          today
            ? "border-blue-300 ring-2 ring-blue-100"
            : tomorrow
              ? "border-amber-200"
              : "border-gray-200"
        }`}
    >
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 bg-gray-50/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CalendarDays className="w-5 h-5 text-gray-400" />
            <div>
              <h3 className="font-semibold text-gray-800">{dia.dia_semana}</h3>
              <p className="text-xs text-gray-500">{formatDate(dia.data)}</p>
            </div>
          </div>
          {chip && (
            <span
              className={`text-xs font-medium px-2.5 py-1 rounded-full ${chip.color}`}
            >
              {chip.label}
            </span>
          )}
        </div>
      </div>

      {/* Cardápio description */}
      {dia.refeicoes.length > 0 && (
        <div className="px-5 py-3 border-b border-gray-100 bg-green-50/30">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Cardápio
          </p>
          <div className="space-y-1.5">
            {dia.refeicoes.map((r) => (
              <div key={r.tipo} className="text-xs text-gray-600">
                <span className="font-medium text-gray-700">{r.nome}:</span>{" "}
                {r.descricao || "—"}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Meal buttons */}
      <div className="p-4 space-y-2">
        {MEALS.map((meal) => {
          const { status, agendamentoId, prazoInfo } = getMealStatus(
            dia.data,
            meal.code,
            agendamentos
          );

          return (
            <MealButton
              key={meal.code}
              meal={meal}
              status={status}
              agendamentoId={agendamentoId}
              prazoInfo={prazoInfo}
              onSchedule={(code) => onSchedule(dia.data, code)}
              onUnschedule={onUnschedule}
            />
          );
        })}
      </div>
    </div>
  );
}
