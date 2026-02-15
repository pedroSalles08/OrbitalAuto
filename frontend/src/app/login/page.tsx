// ── OrbitalAuto · Login Page ────────────────────────────────────

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import LoginForm from "@/components/LoginForm";
import { login, getToken, removeToken, checkAuth, ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();

  // Se já está logado (e sessão ainda válida), redireciona
  useEffect(() => {
    async function check() {
      const token = getToken();
      console.log("[Login] Token on mount:", token ? token.substring(0, 8) + "..." : "null");
      if (!token) return;

      try {
        const status = await checkAuth();
        console.log("[Login] Auth status:", JSON.stringify(status));
        if (status.authenticated) {
          router.replace("/dashboard");
        } else {
          // Token existe mas sessão expirou — limpar
          console.log("[Login] Session expired, clearing token");
          removeToken();
        }
      } catch (err) {
        // Falha na verificação — limpar token inválido
        console.error("[Login] checkAuth error:", err);
        removeToken();
      }
    }
    check();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLogin(cpf: string, senha: string) {
    try {
      const result = await login({ cpf, senha });
      console.log("[Login] Login success, token:", result.token.substring(0, 8) + "...", "nome:", result.nome);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        throw new Error(err.message);
      }
      throw new Error("Erro ao conectar com o servidor. Tente novamente.");
    }
  }

  return <LoginForm onLogin={handleLogin} />;
}
