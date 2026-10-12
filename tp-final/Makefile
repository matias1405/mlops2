# movierec — comandos de la plataforma.
# Si tu usuario no está en el grupo docker:  make <target> DOCKER="sudo docker"
# El ciclo de vida del modelo (descarga, ingesta, entrenamiento, promoción y rollback) se opera desde la UI
# de Airflow, y la primera carga (DAG bootstrap) corre sola al primer arranque: acá solo está la infraestructura.

DOCKER   ?= docker
GIT_SHA  := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
PLATFORM := MOVIEREC_GIT_SHA=$(GIT_SHA) $(DOCKER) compose -p movierec-platform -f compose.platform.yml --env-file platform.env
APP_BASE  = $(DOCKER) compose -f compose.app.yml --env-file platform.env
# Las imágenes no se versionan: se etiquetan por ambiente (:dev, :prod). Lo que tiene versión es el modelo (MLflow).
DEV      := IMAGE_TAG=dev $(APP_BASE) -p movierec-dev --env-file dev.env
PROD     := IMAGE_TAG=prod $(APP_BASE) -p movierec-prod --env-file prod.env

.DEFAULT_GOAL := help
.PHONY: help secrets build-platform up-platform down-platform ps-platform logs-platform build-app \
        up-dev up-prod down-dev down-prod test-ml scan clean-platform

help: ## Lista los comandos disponibles
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

secrets: ## Genera *.env desde las plantillas (no pisa los existentes)
	@python3 scripts/gen_secrets.py platform.env.template dev.env.template prod.env.template

build-platform: secrets ## Construye las imágenes de Airflow y MLflow
	$(PLATFORM) build

up-platform: secrets ## Levanta la plataforma (Postgres, MinIO, Keycloak, MLflow, Airflow)
	$(PLATFORM) up -d --build --wait

down-platform: ## Detiene la plataforma (conserva volúmenes)
	$(PLATFORM) down

ps-platform: ## Estado de los servicios de la plataforma
	$(PLATFORM) ps

logs-platform: ## Logs de la plataforma (SERVICE=airflow-scheduler para uno solo)
	$(PLATFORM) logs -f --tail=100 $(SERVICE)



build-app: secrets ## Construye las imágenes de la app (:dev); los tests corren en el build
	$(DEV) build

up-dev: secrets ## Levanta DEV con las imágenes :dev (modelo @dev)
	$(DEV) up -d --build --wait

up-prod: secrets ## Pasa a PROD las mismas imágenes probadas en DEV (:dev -> :prod, sin rebuild; modelo @production)
	@for s in recommender gateway web; do $(DOCKER) image inspect movierec/$$s:dev >/dev/null 2>&1 || { echo "falta movierec/$$s:dev: corré make up-dev"; exit 1; }; \
	  $(DOCKER) tag movierec/$$s:dev movierec/$$s:prod; done
	$(PROD) up -d --no-build --wait

down-dev: ## Detiene DEV
	$(DEV) down

down-prod: ## Detiene PROD
	$(PROD) down


test-ml: ## Tests de movierec_ml dentro del venv trainer (plataforma levantada)
	$(PLATFORM) exec -w /opt/airflow/ml airflow-scheduler /opt/venvs/trainer/bin/python -m pytest -q -p no:cacheprovider




scan: ## Vulnerabilidades (trivy) de las imágenes; bloquea CRITICAL con fix en las imágenes de la app (TAG=dev|prod)
	@DOCKER="$(DOCKER)" TAG="$(or $(TAG),dev)" bash scripts/scan_images.sh

clean-platform: ## Borra la plataforma Y SUS VOLÚMENES (pide confirmación)
	@read -p "Esto borra Postgres, MinIO y logs de Airflow. ¿Continuar? [y/N] " ok && [ "$$ok" = "y" ]
	$(PLATFORM) down -v

# Targets de desarrollo local (verificaciones y disparo de DAGs desde la terminal), fuera del repo.
-include dev.mk
