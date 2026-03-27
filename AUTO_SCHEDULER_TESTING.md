# Teste do Auto Scheduler

Este guia cobre o fluxo local e o fluxo hospedado no Render.

Estado atual do POC:

- a automacao roda apenas no fim de semana;
- o sistema calcula um slot fixo de sabado por CPF e reutiliza o mesmo horario no domingo como fallback;
- o estado operacional relevante e salvo em `backend/data/auto_schedule.json`;
- a fonte principal de verdade para validacao hospedada e `GET /api/auto-schedule/status`.

## 1. Validacao automatizada

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

## 2. Subir o app local

Use o helper para iniciar o backend com as credenciais do Orbital e com o modo
tecnico desejado:

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\start_auto_scheduler_test.ps1 -Mode dry-run-manual
```

Modos:

- `dry-run-manual`: sobe com `AUTO_SCHEDULE_DRY_RUN=true` e a automacao salva desativada.
- `dry-run-loop`: sobe com `AUTO_SCHEDULE_DRY_RUN=true` e a automacao salva ativada.
- `real-manual`: sobe com `AUTO_SCHEDULE_DRY_RUN=false` e a automacao salva desativada.
- `real-loop`: sobe com `AUTO_SCHEDULE_DRY_RUN=false` e a automacao salva ativada.

Parametros uteis:

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\start_auto_scheduler_test.ps1 `
  -Mode dry-run-loop `
  -Cpf 00000000000 `
  -Password (Read-Host "Senha Orbital" -AsSecureString) `
  -Meals AL,JA `
  -DurationMode 30d
```

## 3. Configurar pela UI

1. Faca login no app.
2. No topo, ao lado do nome do usuario, clique no icone do relogio.
3. Ajuste:
   - ativar/desativar automacao;
   - refeicoes automaticas;
   - validade.
4. Clique em `Salvar`.

O popover mostra em modo somente leitura:

- slot principal do sabado;
- fallback de domingo;
- proxima execucao;
- ultima execucao.

## 4. Teste local sem impacto

1. Suba com `-Mode dry-run-loop`.
2. Faca login no app.
3. Abra o popover e confirme o horario calculado de sabado/domingo.
4. Se estiver no fim de semana e o slot ja tiver passado, o scheduler deve
   rodar uma vez no startup.
5. Se estiver antes do fim de semana, confira apenas `Proxima execucao`.
6. Em `dry-run`, `GET /api/agendamentos` nao deve mostrar itens novos.

## 5. Teste de catch-up

1. Ative a automacao.
2. Reinicie o backend em um destes cenarios:
   - sabado apos o slot calculado;
   - domingo apos o slot calculado, sem sucesso no sabado.
3. O scheduler deve rodar uma vez no startup.
4. Reinicie de novo no mesmo dia.
5. Ele nao deve repetir a mesma fase do fim de semana.

## 6. Smoke test HTTP local

O smoke remoto agora tambem consegue:

- autenticar na barreira simples;
- fazer login no proprio app com CPF e senha;
- salvar uma configuracao minima via API;
- disparar `POST /api/auto-schedule/run`;
- validar automaticamente os criterios da Fase 1 hospedada.

Uso minimo com token manual:

```powershell
python .\backend\smoke_auto_scheduler.py `
  --base-url http://127.0.0.1:8000 `
  --app-token SEU_TOKEN
```

Uso completo com login automatico no app:

```powershell
python .\backend\smoke_auto_scheduler.py `
  --base-url http://127.0.0.1:8000 `
  --app-cpf 00000000000 `
  --app-password SUA_SENHA `
  --apply-minimal-config `
  --config-weekday MON `
  --config-meal AL `
  --run `
  --require-credentials `
  --require-success `
  --validate-hosted-smoke `
  --wait-seconds 5
```

## 7. Render: prerequisitos

No primeiro deploy no Render:

```env
AUTO_SCHEDULE_DRY_RUN=true
AUTO_SCHEDULE_CPF=seu-cpf
AUTO_SCHEDULE_PASSWORD=sua-senha
AUTO_SCHEDULE_CONFIG_PATH=/opt/render/project/src/backend/data/auto_schedule.json
```

Observacoes importantes:

- no `Free`, o Render pode dormir o servico apos 15 minutos sem trafego;
- no `Free`, alteracoes no filesystem local sao perdidas em restart, redeploy ou spin-down;
- a sessao manual do navegador nao precisa ser persistida para a automacao funcionar;
- a configuracao da automacao e os timestamps de tentativa/sucesso precisam sobreviver a restart para evitar comportamento ambiguo.

## 8. Fase 1: Hosted smoke no Free

Objetivo: validar o reconciliador hospedado sem esperar o fim de semana e sem
criar agendamentos reais.

Precondicoes:

- servico atual no Render;
- `AUTO_SCHEDULE_DRY_RUN=true`;
- `AUTO_SCHEDULE_CPF` e `AUTO_SCHEDULE_PASSWORD` configurados;
- credenciais da barreira simples disponiveis, se ela estiver ativa.

Comando recomendado:

```powershell
python .\backend\smoke_auto_scheduler.py `
  --base-url https://SEU-SERVICO.onrender.com `
  --access-user admin `
  --access-pass secret `
  --app-cpf 00000000000 `
  --app-password SUA_SENHA `
  --apply-minimal-config `
  --config-weekday MON `
  --config-meal AL `
  --run `
  --require-credentials `
  --require-success `
  --validate-hosted-smoke `
  --wait-seconds 5
```

Criterios de aprovacao automatizados por `--validate-hosted-smoke`:

- `has_credentials=true` no baseline;
- `run.success=true`;
- `run.finished_at` preenchido;
- `run.trigger='manual'`;
- a execucao informou `used_existing_session=true` ou `login_performed=true`;
- `last_successful_run_at` mudou entre o baseline e o follow-up.

## 9. Fase 2: Janela exploratoria no Free

Objetivo: observar o comportamento automatico hospedado sabendo que o `Free`
nao e um ambiente confiavel para provar execucao autonoma.

Mantendo o servico acordado com polling de status:

```powershell
python .\backend\smoke_auto_scheduler.py `
  --base-url https://SEU-SERVICO.onrender.com `
  --access-user admin `
  --access-pass secret `
  --app-cpf 00000000000 `
  --app-password SUA_SENHA `
  --require-credentials `
  --watch-seconds 14400 `
  --watch-interval-seconds 300
```

Leitura esperada:

- antes do slot, `next_run_at` deve apontar para o slot corrente;
- depois do slot de sabado, o `last_run.trigger` deve virar `primary` ou o
  processo deve fazer catch-up quando acordar;
- no domingo, `fallback` so deve aparecer se o sabado nao tiver sucesso;
- sucesso nesta fase significa apenas "funciona com assistencia".

## 10. Gate para Starter

Suba para `Starter` antes de:

- provar que a automacao executa sozinha no horario;
- deixar a automacao real ligada sem supervisao;
- depender da persistencia local de `auto_schedule.json`.

Motivos:

- `Free` dorme;
- `Free` pode reiniciar a qualquer momento;
- `Free` nao suporta persistent disk;
- `Starter` reduz ruido de cold start e processamento.

## 11. Fase 3: validacao final no Starter

1. Repita primeiro a mesma rotina da Fase 1 ainda em `dry-run`.
2. Rode a janela automatica sem keep-alive externo.
3. Se passar, faca um unico teste real controlado.
4. Confirme por tres sinais:
   - `GET /api/auto-schedule/status`;
   - dashboard normal ou `GET /api/agendamentos`;
   - logs do Render e do login no Orbital.
5. Ao final, desative a automacao ou deixe uma configuracao minima conhecida.

Para inspecionar agendamentos no mesmo fluxo:

```powershell
python .\backend\smoke_auto_scheduler.py `
  --base-url https://SEU-SERVICO.onrender.com `
  --access-user admin `
  --access-pass secret `
  --app-cpf 00000000000 `
  --app-password SUA_SENHA `
  --run `
  --require-success `
  --fetch-agendamentos
```
