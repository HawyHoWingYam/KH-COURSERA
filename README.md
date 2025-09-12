# 🔍 GeminiOCR - AI-Powered Document Processing Platform

一个基于 FastAPI + Next.js 的智能 OCR/文档处理平台，支持多文档类型解析、批处理、WebSocket 实时状态、S3 文件存储与 RDS 数据库，并提供完善的 Docker 化与 CI/CD 流程。

## 🏗️ 架构与能力

**核心组件**
- Backend: FastAPI（含 WebSocket、OpenAPI /docs）
- Frontend: Next.js（App Router）
- Database: PostgreSQL（本地/容器/RDS 皆可）
- Cache: Redis（可选）
- Storage: AWS S3（测试环境自动回退本地）
- AI Engine: Google Gemini

**关键特性**
- 🔍 PDF/图片/ZIP 等多格式解析
- ⚡ WebSocket 实时进度
- 📦 批处理任务与使用统计
- 🏢 多租户文档类型配置
- ☁️ S3/RDS 云集成，支持本地降级
- 📈 导出 Excel

---

## 🚀 本地开发（Anaconda 推荐）

### 依赖
- Anaconda（Python 3.11+）
- Node.js 18+（npm 9+）
- 可选：本地 PostgreSQL / Redis

### 启动 Backend（Terminal 1）
```bash
cd GeminiOCR/backend
conda activate gemini-sandbox
export AWS_ACCESS_KEY_ID=your_aws_access_key_id
export AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
export AWS_DEFAULT_REGION=ap-southeast-1
uvicorn app:app --host 0.0.0.0 --port 8001
```

### 启动 Frontend（Terminal 2）
```bash
cd GeminiOCR/frontend
npm run dev
```

### 访问
- Frontend: http://localhost:3000
- API Docs: http://localhost:8001/docs
- Health: http://localhost:8001/health

---

## 🐳 Docker 部署（开发/生产）

平台提供完整的 Docker 化方案与零停机部署脚本。

### 开发环境（可选）
```bash
# 启动
docker compose -f GeminiOCR/docker-compose.dev.yml up -d

# 查看状态与日志
docker compose -f GeminiOCR/docker-compose.dev.yml ps
docker compose -f GeminiOCR/docker-compose.dev.yml logs -f
```

### 生产部署
```bash
cd GeminiOCR

# 蓝绿部署（推荐）
./deploy.sh blue-green auto     # 智能选择镜像源（Hub 优先）

# 滚动更新
./deploy.sh rolling auto

# 指定版本（从 Docker Hub 拉取）
DEPLOY_VERSION=v1.0.0 ./deploy.sh blue-green hub
```

> 部署脚本会完成：预检查 → 备份 → 构建/拉取镜像 → 蓝绿/滚动部署 → 健康验证 → 清理旧资源。

### Compose 说明
- 推荐 `docker compose`（Compose v2）。
- Compose 文件中的顶层 `version:` 已弃用，已按 v2 规范兼容。

---

## 🔁 CI/CD（GitHub Actions）

完整的四阶段流水线：**功能开发** → **UAT测试** → **生产发布** → **维护回滚**

### 🐳 双仓库架构
- **开发/测试环境**: `karasho62/hya-ocr-sandbox`
  - 触发：`develop` 分支、`feature/*` 分支（仅测试）
  - 用于：UAT、集成测试、开发验证
- **生产环境**: `karasho62/hya-ocr-production` 
  - 触发：`main` 分支、`v*` 标签
  - 用于：生产部署、正式发布

### 🚀 分支策略与触发条件
- **`feature/*`** → 构建测试（不推送镜像）
- **`develop`** → 推送到 sandbox 仓库，UAT 部署
- **`main`** → 推送到 production 仓库
- **`v*.*.*`** → 版本发布到 production 仓库，创建 GitHub Release

### 🏷️ 镜像标签规范
**Sandbox 仓库**:
- `karasho62/hya-ocr-sandbox:backend-develop`
- `karasho62/hya-ocr-sandbox:frontend-develop`

**Production 仓库**:
- `karasho62/hya-ocr-production:backend-v1.0.0`
- `karasho62/hya-ocr-production:frontend-latest`

### 🔐 GitHub Secrets 配置
- `DOCKERHUB_USERNAME`: Docker Hub 用户名
- `DOCKERHUB_TOKEN`: Docker Hub 访问令牌

### 集成测试要点
- 使用 Compose v2 启动 `db / redis / backend / frontend`
- 后端健康探针命中 `/health`，根路径 404 不视为失败
- Postgres 健康检查使用 `-d ${POSTGRES_DB}` 避免噪声日志

### 常见失败与修复
- 推送镜像被拒：确认仓库存在且已 `docker/login-action`
- SARIF 上传被拒：添加 `permissions.security-events: write`，仅在非 PR 上传
- `docker-compose` 未找到：在 CI 使用 `docker compose`
- SQLite/依赖问题：测试时用 `sqlite:////tmp/test.db`；安装 `python-multipart`

---

## 📁 目录结构

```
GeminiOCR/
├── backend/              # FastAPI app
│   ├── app.py            # 主应用（含 WebSocket）
│   ├── config_loader.py  # 配置加载与校验
│   ├── env/.env          # 环境变量（不提交）
│   ├── db/               # 数据库模型与连接
│   └── utils/            # S3/Excel/工具
├── frontend/             # Next.js 应用
│   ├── src/app/
│   └── .env.local
├── deploy.sh             # 零停机部署脚本
└── .github/workflows/ci-cd.yml
```

---

## ⚙️ 配置

### 环境文件
- `backend/env/.env`（后端）
- `frontend/.env.local`（前端）

### 示例（Sandbox）
```bash
# Backend (backend/env/.env)
ENVIRONMENT=sandbox
PORT=8001
DATABASE_URL="postgresql://HYA_OCR:password@hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432/postgres"
S3_BUCKET_NAME=hya-ocr-sandbox
GEMINI_API_KEY_1=your_sandbox_gemini_key

# Frontend (frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8001
```

**注意**
- 不要提交 `.env`、`.env.local`
- 配置优先级：环境变量 > AWS Secrets > .env > 默认值

---

## 🔍 监控与健康
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs
- Health: http://localhost:8001/health
- Frontend: http://localhost:3000

### 运维常用命令（Docker）
```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
curl -f http://localhost/health
```

---

## 🛠️ 故障排除

**镜像推送失败**
```bash
echo $DOCKERHUB_TOKEN | docker login -u $DOCKERHUB_USERNAME --password-stdin
```

**健康检查失败**
```bash
docker compose ps
docker compose logs backend
curl -v http://localhost:8000/health
```

**部署脚本排错**
```bash
cd GeminiOCR
./deploy.sh -h
./deploy.sh blue-green auto 2>&1 | tee deploy.log
```

**镜像拉取失败**
```bash
# 检查 sandbox 镜像
docker manifest inspect karasho62/hya-ocr-sandbox:backend-develop

# 检查 production 镜像
docker manifest inspect karasho62/hya-ocr-production:backend-latest
```

---

## 📜 版本策略
- main → `latest`
- tags（如 `v1.0.0`）→ 语义化版本
- develop/feature 分支：仅构建与测试

---

## 📞 支持
1. 健康检查与日志
2. 环境变量与凭据
3. 参考 `CLAUDE.md` 获取完整开发指南

**Environment Status**: Sandbox ✅  
**Last Updated**: 2025-09-11