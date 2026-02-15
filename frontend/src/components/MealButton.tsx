// ── OrbitalAuto · MealButton ────────────────────────────────────
/**
 * Botão individual de refeição com 3 estados visuais:
 * - available (cinza)  → clicável → agenda
 * - scheduled (verde)  → clicável → desagenda
 * - expired (vermelho) → desabilitado
 */

"use client";

import { useState } from "react";
import { Loader2, Check, X, Clock, Coffee, UtensilsCrossed, Cookie, Moon } from "lucide-react";
import type { MealCode, MealInfo, MealStatus } from "@/types";

// ── Icon Map ────────────────────────────────────────────────────

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Coffee,
  UtensilsCrossed,
  Cookie,
  Moon,
};

interface MealButtonProps {
  meal: MealInfo;
  status: MealStatus;
  agendamentoId?: number;
  prazoInfo?: string;
  onSchedule: (code: MealCode) => Promise<void>;
  onUnschedule: (id: number) => Promise<void>;
}

export default function MealButton({
  meal,
  status,
  agendamentoId,
  prazoInfo,
  onSchedule,
  onUnschedule,
}: MealButtonProps) {
  const [loading, setLoading] = useState(false);

  const Icon = ICON_MAP[meal.icon] || Coffee;

  async function handleClick() {
    if (loading || status === "expired") return;

    setLoading(true);
    try {
      if (status === "scheduled" && agendamentoId) {
        await onUnschedule(agendamentoId);
      } else if (status === "available") {
        await onSchedule(meal.code);
      }
    } finally {
      setLoading(false);
    }
  }

  // ── Visual states ─────────────────────────────────────────────

  const styles = {
    available: {
      button: `bg-gray-50 hover:bg-gray-100 border-gray-200 hover:border-gray-300 
        text-gray-700 hover:shadow-md cursor-pointer`,
      badge: "",
      label: "Agendar",
    },
    scheduled: {
      button: `bg-green-50 hover:bg-green-100 border-green-300 hover:border-green-400
        text-green-800 hover:shadow-md cursor-pointer`,
      badge: "bg-green-500",
      label: "Agendado",
    },
    expired: {
      button: `bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed opacity-60`,
      badge: "bg-red-400",
      label: "Expirado",
    },
  };

  const s = styles[status];

  return (
    <button
      onClick={handleClick}
      disabled={loading || status === "expired"}
      className={`relative flex items-center gap-3 w-full px-4 py-3 rounded-xl border-2 
        transition-all duration-200 ${s.button} disabled:cursor-not-allowed`}
      title={prazoInfo || meal.nome}
    >
      {/* Icon */}
      <div
        className={`shrink-0 rounded-lg p-2 ${
          status === "scheduled"
            ? "bg-green-100"
            : status === "expired"
              ? "bg-gray-100"
              : meal.bgColor
        }`}
      >
        <Icon
          className={`w-5 h-5 ${
            status === "scheduled"
              ? "text-green-600"
              : status === "expired"
                ? "text-gray-400"
                : meal.color
          }`}
        />
      </div>

      {/* Label */}
      <div className="flex-1 text-left">
        <span className="text-sm font-medium block">{meal.nome}</span>
        <span className="text-xs opacity-70">
          {loading
            ? "Processando..."
            : status === "scheduled"
              ? "Clique para cancelar"
              : status === "expired"
                ? prazoInfo || "Prazo expirado"
                : "Clique para agendar"}
        </span>
      </div>

      {/* Status indicator */}
      <div className="shrink-0">
        {loading ? (
          <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
        ) : status === "scheduled" ? (
          <Check className="w-5 h-5 text-green-500" />
        ) : status === "expired" ? (
          <Clock className="w-5 h-5 text-gray-400" />
        ) : (
          <X className="w-5 h-5 text-gray-300" />
        )}
      </div>
    </button>
  );
}
