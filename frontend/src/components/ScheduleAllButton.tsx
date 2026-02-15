// ── OrbitalAuto · ScheduleAllButton ─────────────────────────────
/**
 * Botão destacado para agendar todas as refeições de toda a semana.
 */

"use client";

import { useState } from "react";
import { CalendarCheck, Loader2, AlertTriangle } from "lucide-react";

interface ScheduleAllButtonProps {
  onScheduleAll: () => Promise<{ agendados: number; erros: string[] }>;
}

export default function ScheduleAllButton({
  onScheduleAll,
}: ScheduleAllButtonProps) {
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  async function handleConfirm() {
    setShowConfirm(false);
    setLoading(true);
    try {
      await onScheduleAll();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setShowConfirm(true)}
        disabled={loading}
        className="w-full bg-gradient-to-r from-[#006633] to-green-700 hover:from-green-800 
          hover:to-green-900 disabled:from-gray-400 disabled:to-gray-500
          text-white font-semibold py-4 px-6 rounded-2xl shadow-lg hover:shadow-xl
          transition-all duration-200 flex items-center justify-center gap-3
          cursor-pointer disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader2 className="w-6 h-6 animate-spin" />
            Agendando toda a semana...
          </>
        ) : (
          <>
            <CalendarCheck className="w-6 h-6" />
            Agendar Toda a Semana
          </>
        )}
      </button>

      {/* Confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6 animate-scale-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="bg-amber-100 rounded-full p-2">
                <AlertTriangle className="w-6 h-6 text-amber-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-800">
                Confirmar Agendamento
              </h3>
            </div>

            <p className="text-gray-600 text-sm mb-6">
              Isso vai agendar <strong>todas as 4 refeições</strong> (Lanche da
              Manhã, Almoço, Lanche da Tarde e Jantar) para{" "}
              <strong>todos os dias disponíveis</strong> da semana.
            </p>

            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-xl
                  text-gray-700 hover:bg-gray-50 transition-colors font-medium cursor-pointer"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirm}
                className="flex-1 px-4 py-2.5 bg-[#006633] hover:bg-green-800 
                  text-white rounded-xl transition-colors font-medium cursor-pointer"
              >
                Agendar Tudo
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
