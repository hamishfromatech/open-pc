# Open-PC Dashboard
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Optional REST auth token baked into the build (sent as X-OpenPC-Token)
ARG VITE_OPENPC_TOKEN=""
ENV VITE_OPENPC_TOKEN=$VITE_OPENPC_TOKEN
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]