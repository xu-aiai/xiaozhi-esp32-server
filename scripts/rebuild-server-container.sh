#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/main/xiaozhi-server/docker-compose.yml}"
SERVICE_NAME="${SERVICE_NAME:-xiaozhi-esp32-server}"
CONTAINER_NAME="${CONTAINER_NAME:-xiaozhi-esp32-server}"
DOCKERFILE="${DOCKERFILE:-${REPO_ROOT}/Dockerfile-server}"
BUILD_CONTEXT="${BUILD_CONTEXT:-${REPO_ROOT}}"
PLATFORM="${PLATFORM:-linux/amd64}"
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

log "构建镜像：${IMAGE_NAME}"
docker buildx build \
  --platform "${PLATFORM}" \
  --load \
  -f "${DOCKERFILE}" \
  -t "${IMAGE_NAME}" \
  "${BUILD_CONTEXT}"

log "停止并删除旧容器：${SERVICE_NAME}"
docker compose -f "${COMPOSE_FILE}" rm -sf "${SERVICE_NAME}" >/dev/null 2>&1 || true

if docker ps -a --format '{{.Names}}' | grep -Fxq "${CONTAINER_NAME}"; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
  log "已删除容器：${CONTAINER_NAME}"
else
  log "未找到容器：${CONTAINER_NAME}"
fi

log "重新启动容器：${SERVICE_NAME}"
docker compose -f "${COMPOSE_FILE}" up -d "${SERVICE_NAME}"

log "完成"
