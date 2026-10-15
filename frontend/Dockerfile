# Build: compila a SPA (Vite) a partir do código-fonte — nada de artefato
# pré-compilado commitado no repositório.
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
# Sem package-lock.json commitado ainda (nunca foi gerado com npm install
# de verdade) — "npm ci" exige um lockfile existente e falha sem ele. Usa
# "npm install", que resolve e instala mesmo sem lockfile prévio. Depois
# que alguém rodar "npm install" localmente uma vez e commitar o
# package-lock.json gerado, trocar para "npm ci" (mais rápido e 100%
# reprodutível) é uma melhoria válida.
RUN npm install

COPY . .

# VITE_* é resolvida em tempo de build (o resultado é HTML/JS estático) —
# por isso entra como build arg, não como variável de ambiente do container
# em runtime. Se mudar, é preciso reconstruir esta imagem
# (docker compose build web), não só reiniciar o container.
#
# VITE_API_BASE_URL vazia (padrão) faz o frontend chamar "/api" no mesmo
# host:porta que o navegador usou pra abrir a página — o nginx deste
# container repassa internamente pro serviço "api" (ver nginx.conf).
# Funciona por localhost, IP da rede local ou IP público, sem escolher um
# endereço fixo aqui, e sem precisar expor uma segunda porta. Só defina
# VITE_API_BASE_URL se a API morar num host DIFERENTE do frontend (fora
# deste docker-compose).
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# Runtime: serve o build estático via nginx.
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
