FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL
ARG VITE_ADMIN_PORTAL_URL
ARG VITE_PATIENT_PORTAL_URL
ARG VITE_PORTAL_WS_URL

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ADMIN_PORTAL_URL=$VITE_ADMIN_PORTAL_URL
ENV VITE_PATIENT_PORTAL_URL=$VITE_PATIENT_PORTAL_URL
ENV VITE_PORTAL_WS_URL=$VITE_PORTAL_WS_URL

RUN npm run build:admin  && node scripts/generate-index.mjs dist-admin
RUN npm run build:patient && node scripts/generate-index.mjs dist-patient

RUN echo "=== /app/dist-admin/client/ ===" && ls -la /app/dist-admin/client/
RUN echo "=== /app/dist-patient/client/ ===" && ls -la /app/dist-patient/client/


FROM nginx:1.27-alpine

ARG BUILD_MODE

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist-admin /app/dist-admin
COPY --from=build /app/dist-patient /app/dist-patient

RUN rm -rf /usr/share/nginx/html/* && \
  mkdir -p /usr/share/nginx/html && \
  echo "=== Copying for BUILD_MODE=$BUILD_MODE ===" && \
  if [ "$BUILD_MODE" = "admin" ]; then \
    echo "Looking in /app/dist-admin..." && \
    ls -la /app/dist-admin/ && \
    if [ -d "/app/dist-admin/client" ]; then \
      echo "Using /app/dist-admin/client" && \
      cp -r /app/dist-admin/client/. /usr/share/nginx/html/; \
    elif [ -d "/app/dist-admin/public" ]; then \
      echo "Using /app/dist-admin/public" && \
      cp -r /app/dist-admin/public/. /usr/share/nginx/html/; \
    else \
      echo "Using /app/dist-admin" && \
      cp -r /app/dist-admin/. /usr/share/nginx/html/; \
    fi; \
  elif [ "$BUILD_MODE" = "patient" ]; then \
    echo "Looking in /app/dist-patient..." && \
    ls -la /app/dist-patient/ && \
    if [ -d "/app/dist-patient/client" ]; then \
      echo "Using /app/dist-patient/client" && \
      cp -r /app/dist-patient/client/. /usr/share/nginx/html/; \
    elif [ -d "/app/dist-patient/public" ]; then \
      echo "Using /app/dist-patient/public" && \
      cp -r /app/dist-patient/public/. /usr/share/nginx/html/; \
    else \
      echo "Using /app/dist-patient" && \
      cp -r /app/dist-patient/. /usr/share/nginx/html/; \
    fi; \
  else \
    echo "BUILD_MODE must be 'admin' or 'patient'"; \
    exit 1; \
  fi && \
  echo "=== /usr/share/nginx/html/ ===" && \
  ls -la /usr/share/nginx/html/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
