// ── OrbitalAuto · Root Page (redirect) ──────────────────────────

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { getToken, checkAuth, removeToken } from "@/lib/api";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    async function check() {
      const token = getToken();
      if (!token) {
        router.replace("/login");
        return;
      }

      try {
        const status = await checkAuth();
        if (status.authenticated) {
          router.replace("/dashboard");
        } else {
          removeToken();
          router.replace("/login");
        }
      } catch {
        removeToken();
        router.replace("/login");
      }
    }
    check();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="animate-pulse text-gray-400">Carregando...</div>
    </div>
  );
}
