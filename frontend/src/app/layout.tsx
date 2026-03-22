import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OrbitalAuto — Agendamento de Refeições",
  description:
    "Agendamento automático de refeições no Orbital do IFFarroupilha",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
