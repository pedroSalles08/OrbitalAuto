// ── OrbitalAuto · WeeklyMenu ────────────────────────────────────
/**
 * Componente principal do dashboard.
 * Orquestra o cardápio semanal, agendamentos e ações.
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2, RefreshCw, AlertCircle, CalendarX } from "lucide-react";
import type { DiaCardapio, Agendamento, MealCode, AgendarSelecionadoItem } from "@/types";
import {
  getCardapio,
  getAgendamentos,
  agendar,
  desagendar,
  agendarSelecionados,
  ApiError,
} from "@/lib/api";
import DayCard from "./DayCard";
import SchedulePickerButton from "./SchedulePickerButton";
import { useToast } from "./Toast";

export default function WeeklyMenu() {
  const [cardapio, setCardapio] = useState<DiaCardapio[]>([]);
  const [agendamentosList, setAgendamentosList] = useState<Agendamento[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const { toast } = useToast();

  // ── Fetch data ────────────────────────────────────────────────

  const fetchData = useCallback(
    async (showRefresh = false) => {
      if (showRefresh) setRefreshing(true);
      else setLoading(true);

      setError("");

      try {
        const [cardapioRes, agendamentosRes] = await Promise.all([
          getCardapio(),
          getAgendamentos(),
        ]);

        setCardapio(cardapioRes.semana);
        setAgendamentosList(agendamentosRes.agendamentos);
      } catch (err) {
        const msg =
          err instanceof ApiError
            ? err.message
            : "Erro ao carregar dados";
        setError(msg);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    []
  );

  // Initial load
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchData(true);
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ── Actions ───────────────────────────────────────────────────

  async function handleSchedule(dia: string, code: MealCode) {
    try {
      const result = await agendar({ dia, refeicao: code });
      toast(result.message, "success");
      await fetchData(true);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Erro ao agendar";
      toast(msg, "error");
    }
  }

  async function handleUnschedule(id: number) {
    // Encontrar o agendamento para pegar a data
    const ag = agendamentosList.find((a) => a.id === id);
    try {
      const result = await desagendar(id, ag?.dia);
      toast(result.message, "success");
      await fetchData(true);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Erro ao desagendar";
      toast(msg, "error");
    }
  }

  async function handleScheduleSelected(
    items: AgendarSelecionadoItem[]
  ): Promise<{ agendados: number; erros: string[] }> {
    try {
      const result = await agendarSelecionados(items);
      toast(result.message, result.erros.length > 0 ? "info" : "success");
      await fetchData(true);
      return result;
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Erro ao agendar selecionados";
      toast(msg, "error");
      return { agendados: 0, erros: [msg] };
    }
  }

  // ── Loading state ─────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-10 h-10 text-green-600 animate-spin mb-4" />
        <p className="text-gray-500">Carregando cardápio...</p>
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <p className="text-gray-700 font-medium mb-2">Erro ao carregar</p>
        <p className="text-gray-500 text-sm mb-4 text-center max-w-md">
          {error}
        </p>
        <button
          onClick={() => fetchData()}
          className="bg-[#006633] hover:bg-green-800 text-white px-6 py-2 
            rounded-xl transition-colors font-medium cursor-pointer"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  // ── Empty state ───────────────────────────────────────────────

  if (cardapio.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <CalendarX className="w-12 h-12 text-gray-300 mb-4" />
        <p className="text-gray-700 font-medium mb-2">
          Nenhum cardápio publicado
        </p>
        <p className="text-gray-500 text-sm text-center max-w-md">
          O cardápio da semana ainda não foi publicado no Orbital.
          <br />
          Tente novamente mais tarde.
        </p>
        <button
          onClick={() => fetchData()}
          className="mt-4 text-green-700 hover:text-green-800 text-sm 
            font-medium flex items-center gap-1 cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" />
          Atualizar
        </button>
      </div>
    );
  }

  // ── Main content ──────────────────────────────────────────────

  const scheduledCount = agendamentosList.length;

  return (
    <div className="space-y-6">
      {/* Stats + Refresh */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          <span className="font-medium text-gray-700">{cardapio.length}</span>{" "}
          dia(s) no cardápio •{" "}
          <span className="font-medium text-green-700">{scheduledCount}</span>{" "}
          agendamento(s)
        </div>
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="text-gray-400 hover:text-gray-600 transition-colors p-2 cursor-pointer"
          title="Atualizar"
        >
          <RefreshCw
            className={`w-5 h-5 ${refreshing ? "animate-spin" : ""}`}
          />
        </button>
      </div>

      {/* Schedule Picker */}
      <SchedulePickerButton
        cardapio={cardapio}
        agendamentos={agendamentosList}
        onScheduleSelected={handleScheduleSelected}
      />

      {/* Day Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {cardapio.map((dia) => (
          <DayCard
            key={dia.data}
            dia={dia}
            agendamentos={agendamentosList.filter((a) => a.dia === dia.data)}
            onSchedule={handleSchedule}
            onUnschedule={handleUnschedule}
          />
        ))}
      </div>
    </div>
  );
}
