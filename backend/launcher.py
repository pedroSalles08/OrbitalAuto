# ── OrbitalAuto · Desktop Launcher ────────────────────────────────
"""
Ponto de entrada para o executável desktop.

Encontra uma porta livre, inicia o servidor FastAPI em background
e abre o navegador automaticamente. O console mostra o status.
Ctrl+C encerra tudo.
"""

import os
import sys
import socket
import signal
import threading
import time
import webbrowser

import uvicorn

# Fix console encoding on Windows (PyInstaller resets it)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_free_port(start: int = 18700, end: int = 18800) -> int:
    """Encontra uma porta TCP livre no range indicado."""
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Nenhuma porta livre entre {start} e {end}")


def open_browser(port: int, delay: float = 1.5) -> None:
    """Abre o navegador após um pequeno delay para o servidor iniciar."""
    time.sleep(delay)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Abrindo navegador: {url}\n")
    webbrowser.open(url)


def main() -> None:
    # Força DESKTOP_MODE para o config.py detectar
    os.environ["DESKTOP_MODE"] = "true"

    port = find_free_port()

    # Sobrescreve PORT para o config.py
    os.environ["PORT"] = str(port)

    print("=" * 56)
    print("   OrbitalAuto — Agendamento de Refeições")
    print("   IFFarroupilha · Orbital")
    print("=" * 56)
    print(f"\n   Servidor: http://127.0.0.1:{port}")
    print("   Pressione Ctrl+C para encerrar.\n")

    # Abre o navegador em thread separada
    browser_thread = threading.Thread(
        target=open_browser, args=(port,), daemon=True
    )
    browser_thread.start()

    # Inicia o uvicorn (bloqueia aqui)
    try:
        uvicorn.run(
            "app:app",
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    except KeyboardInterrupt:
        print("\n\n   ✅ OrbitalAuto encerrado. Até mais!")
        sys.exit(0)


if __name__ == "__main__":
    main()
