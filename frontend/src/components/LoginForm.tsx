// ── OrbitalAuto · LoginForm ─────────────────────────────────────

"use client";

import { useState, type FormEvent } from "react";
import { Utensils, Loader2, Eye, EyeOff } from "lucide-react";

interface LoginFormProps {
  onLogin: (cpf: string, senha: string) => Promise<void>;
}

export default function LoginForm({ onLogin }: LoginFormProps) {
  const [cpf, setCpf] = useState("");
  const [senha, setSenha] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // ── CPF mask ──────────────────────────────────────────────────

  function formatCpf(value: string): string {
    const digits = value.replace(/\D/g, "").slice(0, 11);
    if (digits.length <= 3) return digits;
    if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
    if (digits.length <= 9)
      return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
    return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
  }

  function handleCpfChange(value: string) {
    setCpf(formatCpf(value));
    setError("");
  }

  // ── Submit ────────────────────────────────────────────────────

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    const cpfDigits = cpf.replace(/\D/g, "");
    if (cpfDigits.length !== 11) {
      setError("CPF deve ter 11 dígitos");
      return;
    }

    if (!senha.trim()) {
      setError("Digite sua senha");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await onLogin(cpfDigits, senha);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao fazer login");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-900 via-green-800 to-green-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo Card */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center bg-white/10 rounded-2xl p-4 mb-4">
            <Utensils className="w-12 h-12 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white">OrbitalAuto</h1>
          <p className="text-green-200 mt-1">
            Agendamento automático de refeições
          </p>
          <p className="text-green-300/60 text-xs mt-1">
            IFFarroupilha
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6 text-center">
            Acessar com Orbital
          </h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* CPF */}
            <div>
              <label
                htmlFor="cpf"
                className="block text-sm font-medium text-gray-700 mb-1.5"
              >
                CPF
              </label>
              <input
                id="cpf"
                type="text"
                inputMode="numeric"
                placeholder="000.000.000-00"
                value={cpf}
                onChange={(e) => handleCpfChange(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl 
                  focus:ring-2 focus:ring-green-500 focus:border-green-500
                  text-gray-900 placeholder-gray-400 transition-colors"
                disabled={loading}
                autoComplete="username"
              />
            </div>

            {/* Senha */}
            <div>
              <label
                htmlFor="senha"
                className="block text-sm font-medium text-gray-700 mb-1.5"
              >
                Senha
              </label>
              <div className="relative">
                <input
                  id="senha"
                  type={showPassword ? "text" : "password"}
                  placeholder="Sua senha do Orbital"
                  value={senha}
                  onChange={(e) => {
                    setSenha(e.target.value);
                    setError("");
                  }}
                  className="w-full px-4 py-3 pr-12 border border-gray-300 rounded-xl
                    focus:ring-2 focus:ring-green-500 focus:border-green-500
                    text-gray-900 placeholder-gray-400 transition-colors"
                  disabled={loading}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 
                    hover:text-gray-600 transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-xl">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#006633] hover:bg-green-800 disabled:bg-gray-400
                text-white font-semibold py-3 rounded-xl transition-colors
                flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Entrando...
                </>
              ) : (
                "Entrar"
              )}
            </button>
          </form>

          {/* Info */}
          <p className="text-center text-xs text-gray-400 mt-6">
            Use suas credenciais do sistema Orbital.
            <br />
            Seus dados não são armazenados.
          </p>
        </div>
      </div>
    </div>
  );
}
