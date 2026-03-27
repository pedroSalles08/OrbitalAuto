"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import Header from "@/components/Header";
import WeeklyMenu from "@/components/WeeklyMenu";
import { ToastProvider } from "@/components/Toast";
import { checkAuth, getToken, getUserName, logout } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [nome, setNome] = useState("");
  const [checking, setChecking] = useState(true);

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
        setNome(status.nome || getUserName() || "Usuario");
      } catch (err) {
        console.error("[Dashboard] checkAuth error:", err);
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
  }, [router]);

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  if (checking) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
          <p className="text-gray-500 text-sm">Verificando sessao...</p>
        </div>
      </div>
    );
  }

  return (
    <ToastProvider>
      <div className="min-h-screen bg-gray-50">
        <Header nome={nome} onLogout={handleLogout} />

        <main className="max-w-6xl mx-auto px-4 py-6">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-800">
              Cardapio da Semana
            </h2>
            <p className="text-gray-500 text-sm mt-1">
              Visualize o cardapio e agende suas refeicoes com um clique
            </p>
          </div>

          <WeeklyMenu />
        </main>

        <footer className="text-center py-6 text-xs text-gray-400">
          OrbitalAuto • Agendamento automatico de refeicoes • IFFarroupilha
        </footer>
      </div>
    </ToastProvider>
  );
}
