# Keycloak precompilado: las opciones de build (base de datos, health, cache) se fijan acá con `kc.sh build`,
# así cada arranque usa `start --optimized` y se saltea la recompilación (lenta en un disco lento).
FROM quay.io/keycloak/keycloak:26.5@sha256:45ae20191531eb608ddb0b775d012b40d3e4f942697f3214694887dd7c108d13
ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_CACHE=local
RUN /opt/keycloak/bin/kc.sh build
