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

RUN npm run build:admin
RUN npm run build:patient

RUN ls -la /app/
RUN ls -la /app/dist-admin/ || true
RUN ls -la /app/dist-patient/ || true


FROM nginx:1.27-alpine

ARG BUILD_MODE

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist-admin /app/dist-admin
COPY --from=build /app/dist-patient /app/dist-patient

RUN rm -rf /usr/share/nginx/html/* && \
  mkdir -p /usr/share/nginx/html && \
  if [ "$BUILD_MODE" = "admin" ]; then \
    if [ -d "/app/dist-admin/client" ]; then \
      cp -r /app/dist-admin/client/. /usr/share/nginx/html/; \
    else \
      cp -r /app/dist-admin/. /usr/share/nginx/html/; \
    fi; \
  elif [ "$BUILD_MODE" = "patient" ]; then \
    if [ -d "/app/dist-patient/client" ]; then \
      cp -r /app/dist-patient/client/. /usr/share/nginx/html/; \
    else \
      cp -r /app/dist-patient/. /usr/share/nginx/html/; \
    fi; \
  else \
    echo "BUILD_MODE must be 'admin' or 'patient'"; \
    exit 1; \
  fi && \
  ls -la /usr/share/nginx/html/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
