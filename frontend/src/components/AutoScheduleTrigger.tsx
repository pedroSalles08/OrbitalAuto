"use client";

import { Clock3, Loader2 } from "lucide-react";

interface AutoScheduleTriggerProps {
  active: boolean;
  expired: boolean;
  loading: boolean;
  open: boolean;
  onClick: () => void;
}

export default function AutoScheduleTrigger({
  active,
  expired,
  loading,
  open,
  onClick,
}: AutoScheduleTriggerProps) {
  const label = loading ? "Carregando..." : active ? "Ativa" : expired ? "Expirada" : "Inativa";

  const containerClasses = active
    ? "border-emerald-200 bg-white text-[#006633] shadow-sm hover:bg-emerald-50"
    : expired
      ? "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"
      : "border-white/15 bg-white/10 text-white hover:bg-white/15";

  const iconClasses = active
    ? "bg-emerald-50 text-[#006633]"
    : expired
      ? "bg-amber-100 text-amber-800"
      : "bg-white/10 text-white";

  const dotClasses = active
    ? "bg-emerald-500"
    : expired
      ? "bg-amber-500"
      : "bg-slate-300";

  const subLabelClasses = active ? "text-[#006633]" : expired ? "text-amber-800" : "text-green-100";

  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      aria-label={`Agendamento automatico ${label.toLowerCase()}`}
      className={`inline-flex h-11 items-center gap-2 rounded-xl border px-2.5 transition-all sm:px-3 ${
        open ? "ring-2 ring-white/25" : ""
      } ${containerClasses}`}
    >
      <span className={`relative flex h-8 w-8 items-center justify-center rounded-lg ${iconClasses}`}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clock3 className="h-4 w-4" />}
        {!loading ? (
          <span className={`absolute right-1 top-1 h-2 w-2 rounded-full ${dotClasses}`} />
        ) : null}
      </span>

      <span className="hidden min-w-[92px] flex-col items-start text-left leading-tight sm:flex">
        <span className="text-sm font-semibold">Automacao</span>
        <span className={`text-[11px] ${subLabelClasses}`}>{label}</span>
      </span>
    </button>
  );
}
