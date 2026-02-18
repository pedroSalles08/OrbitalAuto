@echo off
REM ── OrbitalAuto · Build Script ──────────────────────────────────
REM Builds the portable OrbitalAuto.exe
REM Requirements: Node.js, npm, Python 3.10+, pip
REM ────────────────────────────────────────────────────────────────

setlocal enabledelayedexpansion

set ROOT=%~dp0..
set FRONTEND=%ROOT%\frontend
set BACKEND=%ROOT%\backend

echo.
echo ===============================================
echo   OrbitalAuto — Build
echo ===============================================
echo.

REM ── Step 1: Build frontend ──────────────────────────────────────
echo [1/4] Building frontend (Next.js static export)...
cd /d "%FRONTEND%"

call npm install
if %ERRORLEVEL% neq 0 (
    echo ERRO: npm install falhou!
    pause
    exit /b 1
)

call npx next build
if %ERRORLEVEL% neq 0 (
    echo ERRO: next build falhou!
    pause
    exit /b 1
)

REM ── Step 2: Copy "out" to backend ──────────────────────────────
echo.
echo [2/4] Copying static build to backend...
if exist "%BACKEND%\out" rmdir /s /q "%BACKEND%\out"
xcopy /E /I /Q "%FRONTEND%\out" "%BACKEND%\out" >nul
if %ERRORLEVEL% neq 0 (
    echo ERRO: Falha ao copiar frontend build!
    pause
    exit /b 1
)
echo     Copied to backend\out\

REM ── Step 3: Install Python deps ────────────────────────────────
echo.
echo [3/4] Installing Python dependencies...
cd /d "%BACKEND%"

pip install -r requirements.txt pyinstaller --quiet
if %ERRORLEVEL% neq 0 (
    echo ERRO: pip install falhou!
    pause
    exit /b 1
)

REM ── Step 4: PyInstaller ────────────────────────────────────────
echo.
echo [4/4] Building executable with PyInstaller...
pyinstaller --clean --noconfirm OrbitalAuto.spec
if %ERRORLEVEL% neq 0 (
    echo ERRO: PyInstaller falhou!
    pause
    exit /b 1
)

REM ── Done ───────────────────────────────────────────────────────
echo.
echo ===============================================
echo   BUILD CONCLUIDO!
echo.
echo   Executavel: backend\dist\OrbitalAuto.exe
echo.
echo   Para usar: execute OrbitalAuto.exe
echo   O navegador abrira automaticamente.
echo ===============================================
echo.
pause
