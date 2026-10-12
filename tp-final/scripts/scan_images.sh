#!/usr/bin/env bash
# Escaneo de vulnerabilidades (trivy) de las imágenes propias. Cuenta CRITICAL/HIGH con fix disponible
# (--ignore-unfixed: las que no tienen fix no son accionables). Falla si hay CRITICAL no justificadas en
# .trivyignore. Uso: make scan [TAG=dev|prod]
set -euo pipefail
DOCKER=${DOCKER:-docker}
TAG=${TAG:-dev}
TRIVY="$DOCKER run --rm -v /var/run/docker.sock:/var/run/docker.sock:ro -v movierec-trivy-cache:/root/.cache -v $PWD/.trivyignore:/.trivyignore:ro aquasec/trivy@sha256:33f816d414b9d582d25bb737ffa4a632ae34e222f7ec1b50252cef0ce2266006"
# La app (expuesta: web es pública) bloquea; la plataforma (sin puertos públicos) se reporta: sus riesgos
# aceptados y mitigaciones están en docs/security.md.
GATED="movierec/recommender:$TAG movierec/gateway:$TAG movierec/web:$TAG"
REPORTED="movierec/airflow:2.10.4 movierec/mlflow:2.19.0"
IMAGES="$GATED $REPORTED"
mkdir -p reports/security
printf "%-34s %8s %6s  %s\n" IMAGEN CRITICAL HIGH POLÍTICA
crit_total=0
for img in $IMAGES; do
  out="reports/security/$(echo $img | tr '/:' '__').json"
  $TRIVY image --quiet --timeout 20m --scanners vuln --severity CRITICAL,HIGH --ignore-unfixed --ignorefile /.trivyignore --format json "$img" > "$out"
  read c h < <(python3 -c "import json,sys;d=json.load(open('$out'));v=[x for r in d.get('Results',[]) for x in r.get('Vulnerabilities') or []];print(sum(x['Severity']=='CRITICAL' for x in v),sum(x['Severity']=='HIGH' for x in v))")
  case " $GATED " in *" $img "*) pol="bloquea"; crit_total=$((crit_total + c)) ;; *) pol="reporta (docs/security.md)" ;; esac
  printf "%-34s %8s %6s  %s\n" "$img" "$c" "$h" "$pol"
done
echo "detalle: reports/security/*.json"
[ "$crit_total" -eq 0 ] || { echo "Hay $crit_total CRITICAL con fix disponible en imágenes de la app: actualizar o justificar en .trivyignore"; exit 1; }
echo "Imágenes de la app sin CRITICAL con fix disponible."
