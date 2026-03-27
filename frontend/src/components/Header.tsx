// ── OrbitalAuto · Header ────────────────────────────────────────

"use client";

import { LogOut, Utensils } from "lucide-react";
import AutoScheduleControl from "./AutoScheduleControl";

interface HeaderProps {
  nome: string;
  onLogout: () => void;
}

export default function Header({ nome, onLogout }: HeaderProps) {
  return (
    <header className="bg-[#006633] text-white shadow-lg">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        {/* Logo + Title */}
        <div className="flex items-center gap-3">
          <div className="bg-white/20 rounded-lg p-2">
            <Utensils className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold leading-tight">OrbitalAuto</h1>
            <p className="text-xs text-green-200 leading-tight">
              Agendamento de Refeições
            </p>
          </div>
        </div>

        {/* User info + Logout */}
        <div className="flex items-center gap-4">
          <span className="text-sm text-green-100 hidden sm:block">
            {nome}
          </span>
          <AutoScheduleControl />
          <button
            onClick={onLogout}
            className="flex items-center gap-2 bg-white/15 hover:bg-white/25 
              text-sm px-3 py-2 rounded-lg transition-colors cursor-pointer"
            title="Sair"
          >
            <LogOut className="w-4 h-4" />
            <span className="hidden sm:inline">Sair</span>
          </button>
        </div>
      </div>
    </header>
  );
}
