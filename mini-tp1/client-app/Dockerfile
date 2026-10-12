# ---- build ----
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293   AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# Fija el backend a consumir (FastAPI Staging o Production) en build time.
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ---- serve ----
FROM nginx:alpine@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913 
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
