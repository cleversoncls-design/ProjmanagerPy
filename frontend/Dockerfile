# Build: compila a SPA (Vite) a partir do código-fonte — nada de artefato
# pré-compilado commitado no repositório.
FROM node:20-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Variáveis VITE_* são resolvidas em tempo de build (o resultado é HTML/JS
# estático) — por isso entram como build arg, não como variável de ambiente
# do container em runtime. Se o endereço da API mudar, é preciso reconstruir
# esta imagem (docker compose build web), não só reiniciar o container.
ARG VITE_API_BASE_URL=http://localhost:3035
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# Runtime: serve o build estático via nginx.
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
