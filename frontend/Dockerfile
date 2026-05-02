FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG BUILD_MODE
ARG VITE_API_BASE_URL
ARG VITE_ADMIN_PORTAL_URL
ARG VITE_PATIENT_PORTAL_URL
ARG VITE_PORTAL_WS_URL

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_ADMIN_PORTAL_URL=$VITE_ADMIN_PORTAL_URL
ENV VITE_PATIENT_PORTAL_URL=$VITE_PATIENT_PORTAL_URL
ENV VITE_PORTAL_WS_URL=$VITE_PORTAL_WS_URL

RUN if [ "$BUILD_MODE" = "admin" ]; then npm run build:admin; \
  elif [ "$BUILD_MODE" = "patient" ]; then npm run build:patient; \
  else echo "BUILD_MODE must be 'admin' or 'patient'"; exit 1; fi


FROM nginx:1.27-alpine

ARG BUILD_MODE

COPY --from=build /app/dist-admin/client /tmp/admin
COPY --from=build /app/dist-patient/client /tmp/patient

RUN rm -rf /usr/share/nginx/html/* && \
  if [ "$BUILD_MODE" = "admin" ]; then cp -a /tmp/admin/. /usr/share/nginx/html/; \
  elif [ "$BUILD_MODE" = "patient" ]; then cp -a /tmp/patient/. /usr/share/nginx/html/; \
  else echo "BUILD_MODE must be 'admin' or 'patient'"; exit 1; fi

EXPOSE 80
