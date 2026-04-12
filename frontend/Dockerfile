FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_CHURN_API_URL="/churn-api"
ARG VITE_AGENT_API_URL="/agent-api"
ENV VITE_CHURN_API_URL=$VITE_CHURN_API_URL
ENV VITE_AGENT_API_URL=$VITE_AGENT_API_URL
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
