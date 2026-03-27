# Teste do Auto-Schedule

Guia atualizado para o modo hospedado multiusuario.

## Estado atual

- a automacao roda apenas no fim de semana;
- cada CPF recebe dois horarios deterministas independentes:
  - `primary` no sabado entre `00:00` e `23:59`;
  - `fallback` no domingo entre `00:00` e `11:59`;
- o `fallback` so roda se o sabado nao tiver sucesso;
- configuracao, credenciais criptografadas e timestamps ficam no store definido
  por `AUTO_SCHEDULE_STORE_PATH`;
- a referencia principal de validacao hospedada e
  `GET /api/auto-schedule/status`.

## 1. Validacao local

```powershell
cd backend
python -m unittest test_auto_scheduler
python -m unittest test_auto_schedule_api
python -m unittest test_smoke_auto_scheduler
python -m compileall .
cd ..\frontend
npm run lint
npm run build
cd ..
```

## 2. Conferencia na UI

1. Faca login no app.
2. No topo, ao lado do nome do usuario, clique no icone do relogio.
3. Abra o painel e confira:
   - horario do sabado;
   - horario do domingo;
   - domingo sempre antes de `12:00`;
   - proxima execucao;
   - ultima execucao.
4. Salve a senha do Orbital e uma configuracao minima.

## 3. Prerequisitos no Render Starter

```env
DESKTOP_MODE=true
DEBUG=false
MAX_SESSIONS=100
SESSION_EXPIRY_HOURS=4
ENABLE_DEBUG_ROUTES=false
BASIC_AUTH_USER=admin
BASIC_AUTH_PASS=troque-esta-senha

AUTO_SCHEDULE_DRY_RUN=true
AUTO_SCHEDULE_TIMEZONE=America/Sao_Paulo
AUTO_SCHEDULE_LOOKAHEAD_DAYS=7
AUTO_SCHEDULE_STORE_PATH=/var/data/orbitalauto/auto_schedule_profiles.json
AUTO_SCHEDULE_ENCRYPTION_KEY=sua-chave-fernet-estavel
```

Tambem e necessario:

- plano `Starter`;
- `Persistent Disk` anexado em `/var/data/orbitalauto`;
- uma unica instancia;
- cada usuario salvar a propria senha do Orbital no painel da automacao.

## 4. Smoke hospedado em dry-run

Objetivo: validar persistencia, API e execucao manual sem criar agendamentos reais.

```powershell
cd C:\Users\Usuario\Desktop\pessoal\OrbitalAuto\backend

python .\smoke_auto_scheduler.py `
  --base-url https://SEU-SERVICO.onrender.com `
  --access-user SEU_BASIC_AUTH_USER `
  --access-pass SEU_BASIC_AUTH_PASS `
  --app-cpf SEU_CPF `
  --app-password SUA_SENHA_ORBITAL `
  --apply-minimal-config `
  --config-weekday MON `
  --config-meal AL `
  --run `
  --require-credentials `
  --require-success `
  --validate-hosted-smoke `
  --wait-seconds 5
```

Criterios esperados:

- `has_credentials=true`;
- `run.success=true`;
- `run.finished_at` preenchido;
- `last_successful_run_at` atualizado;
- `primary_run_time` visivel;
- `fallback_run_time` visivel e `< 12:00`.

## 5. Teste de persistencia

1. No Render, faca `Manual Deploy -> Restart service`.
2. Reabra o site.
3. Confirme que:
   - a automacao continua salva;
   - a senha continua marcada como salva;
   - os horarios de sabado/domingo continuam iguais para aquele CPF.
4. Rode o smoke hospedado novamente.

## 6. Virada para modo real

1. Troque `AUTO_SCHEDULE_DRY_RUN=false`.
2. Salve as env vars.
3. Faca novo deploy.
4. Revalide `GET /api/health`.
5. Habilite a automacao real primeiro apenas na sua conta.
6. So depois de um ciclo real validado libere para outros usuarios.

## 7. Leitura esperada do comportamento automatico

- antes do slot de sabado, `next_run_at` aponta para o horario principal;
- depois do slot de sabado, se nao houve sucesso, o domingo passa a ser o
  proximo alvo;
- no domingo, o painel mostra um horario proprio antes de `12:00`;
- se o servico reiniciar depois do horario de domingo, mas ainda no domingo,
  o scheduler faz catch-up uma unica vez;
- se esse catch-up ocorrer apos `17:00`, a mensagem da ultima execucao deve
  avisar que a segunda-feira pode ja estar fora da janela do Orbital.
