"use client";

import type { ReactNode } from "react";
import { Loader2, X } from "lucide-react";

interface AutoScheduleDialogProps {
  open: boolean;
  loading: boolean;
  saving: boolean;
  saveDisabled: boolean;
  footerSummary: string;
  onClose: () => void;
  onSave: () => void;
  children: ReactNode;
}

export default function AutoScheduleDialog({
  open,
  loading,
  saving,
  saveDisabled,
  footerSummary,
  onClose,
  onSave,
  children,
}: AutoScheduleDialogProps) {
  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[80] bg-slate-950/45 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="flex min-h-full items-end justify-center p-0 sm:items-center sm:p-6">
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="auto-schedule-title"
          className="flex max-h-[88vh] w-full flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl animate-slide-up sm:max-w-4xl sm:rounded-3xl sm:animate-scale-in"
          onMouseDown={(event) => event.stopPropagation()}
        >
          <header className="border-b border-slate-200 bg-slate-50 px-5 py-5 sm:px-6">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#006633]">
                  Automacao semanal
                </p>
                <h2 id="auto-schedule-title" className="mt-2 text-lg font-semibold text-slate-950 sm:text-xl">
                  Agendamento automatico
                </h2>
                <p className="mt-1 max-w-2xl text-sm text-slate-500">
                  Escolha exatamente quais combinacoes de dia e refeicao o sistema deve tentar agendar no fim de semana.
                </p>
              </div>

              <button
                type="button"
                onClick={onClose}
                className="rounded-xl border border-slate-200 p-2 text-slate-500 transition-colors hover:bg-white hover:text-slate-800"
                aria-label="Fechar painel"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-5 py-4 sm:px-6 sm:py-6">
            {loading ? (
              <div className="mb-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <Loader2 className="h-4 w-4 animate-spin text-[#006633]" />
                Carregando configuracao e pre-visualizacao...
              </div>
            ) : null}

            {children}
          </div>

          <footer className="border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-slate-900">{footerSummary}</p>
                <p className="mt-1 text-xs text-slate-500">
                  As alteracoes so entram em vigor depois de salvar.
                </p>
              </div>

              <div className="flex flex-col-reverse gap-2 sm:flex-row">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={saving}
                  className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-white disabled:opacity-60"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={onSave}
                  disabled={saveDisabled}
                  className="inline-flex min-w-[160px] items-center justify-center gap-2 rounded-xl bg-[#006633] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-green-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Salvando
                    </>
                  ) : (
                    "Salvar automacao"
                  )}
                </button>
              </div>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}
