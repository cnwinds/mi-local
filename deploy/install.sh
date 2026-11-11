#!/bin/sh
# One-line install of mi-local (and go2rtc for cameras) with Docker Compose:
#   curl -fsSL https://raw.githubusercontent.com/cnwinds/mi-local/main/deploy/install.sh | sh
# Options (environment variables):
#   MI_LOCAL_DIR     install directory, default ~/mi-local
#   MI_LOCAL_MIRROR  image registry mirror, e.g. ghcr.nju.edu.cn when ghcr.io is slow
set -e

DIR="${MI_LOCAL_DIR:-$HOME/mi-local}"
RAW="https://raw.githubusercontent.com/cnwinds/mi-local/main"

command -v docker >/dev/null 2>&1 || { echo "需要先安装 Docker：https://docs.docker.com/engine/install/"; exit 1; }
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "需要 Docker Compose：https://docs.docker.com/compose/install/"; exit 1
fi

fetch() {
  if command -v curl >/dev/null 2>&1; then curl -fsSL "$1" -o "$2"; else wget -qO "$2" "$1"; fi
}

mkdir -p "$DIR/go2rtc"
cd "$DIR"
[ -f docker-compose.yml ] || fetch "$RAW/docker-compose.yml" docker-compose.yml
# go2rtc must find this before its first start: without it, it serves an unprotected admin page to the network.
[ -f go2rtc/go2rtc.yaml ] || fetch "$RAW/deploy/go2rtc.yaml" go2rtc/go2rtc.yaml
if [ -n "$MI_LOCAL_MIRROR" ]; then
  sed -i "s#ghcr.io/cnwinds/mi-local#$MI_LOCAL_MIRROR/cnwinds/mi-local#" docker-compose.yml
fi

$COMPOSE pull
$COMPOSE up -d

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -n "$IP" ] || IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}')
echo
echo "mi-local 已启动：http://${IP:-<本机 IP>}:8080"
echo "请在 1 小时内用浏览器打开它，点「开始使用」，这台浏览器就成为管理员。"
echo "安装目录：$DIR（数据在 $DIR/data，里面有设备密钥，备份时注意保密）"
