# Deploy minimo na web

Este projeto pode ser publicado como um unico servico web, mantendo o
backend FastAPI servindo o frontend exportado.

## Plataforma recomendada

- Render Web Service
- Railway Service

As duas podem usar o `Dockerfile` da raiz sem separar frontend e backend.

## Variaveis de ambiente

Defina estas variaveis no servico hospedado:

```env
DESKTOP_MODE=true
DEBUG=false
MAX_SESSIONS=100
SESSION_EXPIRY_HOURS=4
ENABLE_DEBUG_ROUTES=false
BASIC_AUTH_USER=admin
BASIC_AUTH_PASS=troque-esta-senha
```

Opcional:

```env
ORBITAL_BASE_URL=https://orbital.iffarroupilha.edu.br
```

Para o auto schedule hospedado multiusuario, adicione tambem:

```env
AUTO_SCHEDULE_DRY_RUN=false
AUTO_SCHEDULE_TIMEZONE=America/Sao_Paulo
AUTO_SCHEDULE_LOOKAHEAD_DAYS=7
AUTO_SCHEDULE_STORE_PATH=/var/data/orbitalauto/auto_schedule_profiles.json
AUTO_SCHEDULE_ENCRYPTION_KEY=sua-chave-fernet-estavel
```

## Render

1. Crie um `Web Service`.
2. Escolha deploy via `Dockerfile`.
3. Use a raiz do repositorio como contexto.
4. Defina as variaveis de ambiente acima.
5. Anexe um `Persistent Disk`, por exemplo em `/var/data/orbitalauto`.
6. Mantenha uma unica instancia.
7. Use a URL padrao do Render para o primeiro teste.

## Railway

1. Crie um novo service a partir do repositorio.
2. Deixe o Railway detectar o `Dockerfile`.
3. Defina as mesmas variaveis de ambiente.
4. Publique com uma unica instancia e sem autoscaling.

## Comportamento esperado

- A URL publica abre a barreira simples de acesso primeiro.
- Depois da barreira, o fluxo da aplicacao segue como no desktop atual.
- Se o servico reiniciar ou dormir, a sessao Orbital em memoria sera perdida
  e sera necessario fazer login novamente.
- O auto scheduler continua tentando reutilizar a sessao ativa do usuario
  quando ela existir, mas tambem pode fazer login tecnico com a senha salva
  de forma criptografada para aquele CPF.
- A configuracao funcional da automacao nao fica mais em env vars. Ela e salva
  por CPF em `AUTO_SCHEDULE_STORE_PATH`.
- O disparo automatico roda apenas no fim de semana: slot principal no sabado
  e fallback no domingo, ambos definidos automaticamente a partir do CPF do
  usuario autenticado.
- Sem `AUTO_SCHEDULE_ENCRYPTION_KEY`, o site continua funcionando, mas o
  salvamento da automacao multiusuario falha.
- Sem `Persistent Disk`, configuracoes, timestamps e credenciais podem ser
  perdidos em restart ou deploy.

## Observacoes

- A barreira simples usa cookie assinado para nao conflitar com o
  `Authorization: Bearer` que a propria aplicacao usa para a sessao do usuario.
- Os endpoints `/api/debug*` ficam indisponiveis por padrao.
- Os endpoints `/api/auto-schedule/config`, `/api/auto-schedule/status` e
  `/api/auto-schedule/run` ficam atras da mesma barreira simples quando ela
  esta habilitada e tambem exigem sessao autenticada do OrbitalAuto.
- Cada usuario passa a salvar a propria senha do Orbital na UI do auto
  schedule. A senha e armazenada de forma criptografada no servidor.
- O deploy continua monolitico: `frontend/out` e servido pelo backend no
  mesmo dominio.
