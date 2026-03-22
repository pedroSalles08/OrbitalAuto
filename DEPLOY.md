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
MAX_SESSIONS=1
SESSION_EXPIRY_HOURS=4
ENABLE_DEBUG_ROUTES=false
BASIC_AUTH_USER=admin
BASIC_AUTH_PASS=troque-esta-senha
```

Opcional:

```env
ORBITAL_BASE_URL=https://orbital.iffarroupilha.edu.br
```

## Render

1. Crie um `Web Service`.
2. Escolha deploy via `Dockerfile`.
3. Use a raiz do repositorio como contexto.
4. Defina as variaveis de ambiente acima.
5. Mantenha uma unica instancia.
6. Use a URL padrao do Render para o primeiro teste.

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

## Observacoes

- A barreira simples usa cookie assinado para nao conflitar com o
  `Authorization: Bearer` que a propria aplicacao usa para a sessao do usuario.
- Os endpoints `/api/debug*` ficam indisponiveis por padrao.
- O deploy continua monolitico: `frontend/out` e servido pelo backend no
  mesmo dominio.
