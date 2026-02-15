// ── OrbitalAuto · Dashboard Page ────────────────────────────────

"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import WeeklyMenu from "@/components/WeeklyMenu";
import { ToastProvider } from "@/components/Toast";
import { getToken, getUserName, logout, checkAuth } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [nome, setNome] = useState("");
  const [checking, setChecking] = useState(true);

  // ── Auth check ────────────────────────────────────────────────

  useEffect(() => {
    async function verify() {
      const token = getToken();
      console.log("[Dashboard] Token:", token ? token.substring(0, 8) + "..." : "null");

      if (!token) {
        console.log("[Dashboard] No token, redirecting to login");
        router.replace("/login");
        return;
      }

      try {
        const status = await checkAuth();
        console.log("[Dashboard] Auth status:", JSON.stringify(status));
        if (!status.authenticated) {
          console.log("[Dashboard] Not authenticated, redirecting to login");
          router.replace("/login");
          return;
        }
        setNome(status.nome || getUserName() || "Usuário");
      } catch (err) {
        console.error("[Dashboard] checkAuth error:", err);
        // Se falhar, tenta usar nome do localStorage
        const savedName = getUserName();
        if (savedName) {
          setNome(savedName);
        } else {
          console.log("[Dashboard] No saved name, redirecting to login");
          router.replace("/login");
          return;
        }
      }

      setChecking(false);
    }

    verify();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Logout ────────────────────────────────────────────────────

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  // ── Loading ───────────────────────────────────────────────────

  if (checking) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
          <p className="text-gray-500 text-sm">Verificando sessão...</p>
        </div>
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────

  return (
    <ToastProvider>
      <div className="min-h-screen bg-gray-50">
        <Header nome={nome} onLogout={handleLogout} />

        <main className="max-w-6xl mx-auto px-4 py-6">
          {/* Title */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-800">
              Cardápio da Semana
            </h2>
            <p className="text-gray-500 text-sm mt-1">
              Visualize o cardápio e agende suas refeições com um clique
            </p>
          </div>

          {/* Content */}
          <WeeklyMenu />
        </main>

        {/* Footer */}
        <footer className="text-center py-6 text-xs text-gray-400">
          OrbitalAuto • Agendamento automático de refeições • IFFarroupilha
        </footer>
      </div>
    </ToastProvider>
  );
}
