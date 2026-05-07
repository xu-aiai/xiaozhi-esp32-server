#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/../docker-compose_all.yml}"
SERVICE_NAME="${SERVICE_NAME:-xiaozhi-esp32-server}"
CONTAINER_NAME="${CONTAINER_NAME:-xiaozhi-esp32-server}"
DOCKERFILE="${DOCKERFILE:-${REPO_ROOT}/Dockerfile-server}"
BUILD_CONTEXT="${BUILD_CONTEXT:-${REPO_ROOT}}"
IMAGE_NAME="${IMAGE_NAME:-xiaozhi-esp32-server:llm-debug-20260507}"

log() {
  printf '[rebuild-server] %s\n' "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf '缺少命令：%s\n' "$1" >&2
    exit 1
  fi
}

require_command docker

if [ ! -f "${COMPOSE_FILE}" ]; then
  printf 'compose 文件不存在：%s\n' "${COMPOSE_FILE}" >&2
  exit 1
fi

if [ ! -f "${DOCKERFILE}" ]; then
  printf 'Dockerfile 不存在：%s\n' "${DOCKERFILE}" >&2
  exit 1
fi

log "停止服务：${SERVICE_NAME}"
docker compose -f "${COMPOSE_FILE}" stop "${SERVICE_NAME}"

log "删除容器：${CONTAINER_NAME}"
docker rm "${CONTAINER_NAME}"

log "删除镜像：${IMAGE_NAME}"
docker rmi "${IMAGE_NAME}"

log "构建镜像：${IMAGE_NAME}"
docker build -f "${DOCKERFILE}" -t "${IMAGE_NAME}" "${BUILD_CONTEXT}"

log "重新启动容器：${SERVICE_NAME}"
docker compose -f "${COMPOSE_FILE}" up -d "${SERVICE_NAME}"

log "完成"
