# mi-local

米家设备的本地控制中心：在家里的 NAS / 小主机上运行，断网时无线开关、灯、窗帘的联动照常工作。

- Wi-Fi 设备（Yeelight 吸顶灯、飞利浦筒灯等）走 miIO 局域网协议直接控制
- 无线开关、窗帘、插座接在小米网关 2（`lumi.gateway.v3`）下，走网关局域网协议，按键事件实时推送
- 手机端是 PWA，界面参照米家：按房间分组的设备卡片、“如果…就…”自动化
- 可选登录米家账号，自动同步设备名称、房间、token 和 IP；断网时沿用上次同步的数据

## 部署（Docker，支持 arm64 / amd64）

镜像由 GitHub Actions 自动构建：`ghcr.io/cnwinds/mi-local:latest`。

```bash
mkdir -p ~/mi-local && cd ~/mi-local
# 下载 docker-compose.yml 后：
docker compose pull
docker compose up -d
```

必须使用 `network_mode: host`，并且设备与网关 2 在同一网段：网关事件是 `224.0.0.50:9898` 组播，不会跨网段。

### 数据目录

所有配置在 `./data`：

| 文件 | 内容 |
|---|---|
| `devices.json` | 设备列表；网关 2 的记录里含局域网密钥 `lan_key` |
| `rules.json` | 自动化规则 |
| `settings.json` | 房间顺序等 |
| `cloud.json` | 米家账号登录状态（敏感） |

首次部署时，把已配置好的 `data` 目录整个拷到设备上即可。网关 2 的局域网密钥需通过 miIO 命令 `set_lumi_dpf_aes_key` 设置一次，见 `tools/`。

## 本地开发

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt pytest
.venv/bin/pip install --no-deps python-miio==0.5.12
cd backend && ../.venv/bin/python -m homehub       # http://localhost:8080

cd frontend && npm install && npm run dev          # 开发时前端，代理到 8080
```

国内构建镜像可切换软件源：

```bash
docker build --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
             --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t mi-local .
```
