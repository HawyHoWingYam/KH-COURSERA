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

### 🧭 映射配置流程（单源 / 多源）

新的映射体系以 **订单项（OcrOrderItem）** 为核心，支持两种模式：

| 模式 | 使用场景 | 输入准备 | 加工流程 |
| --- | --- | --- | --- |
| **Single Source** | 单份主单 PDF 对照 OneDrive Master CSV 生成结果 | 上传主单 PDF | OCR ➜ DataFrame ➜ 按 `external_join_keys` 与 Master CSV JOIN |
| **Multiple Source** | 主单 + N 张副单合并后再对照 Master CSV | 上传主单 PDF + 通过月份批量附加副单 | OCR ➜ 主单/副单按 `internal_join_key` 合并 ➜ 再与 Master CSV JOIN |

主 CSV 不再通过“订单级映射文件”上传，系统会直接从 OneDrive 固定目录读取，例如 `HYA-OCR/Master Data/TELECOM_USERS.csv`。管理员可在后台配置默认模板与覆盖策略，前台用户则在每个订单项上查看/调整配置。

#### 模板与默认值

- **Mapping Template**：可重用的映射模板，配置主 CSV 路径、外部/内部 JOIN 键、列别名等，可按公司/文档类型限定范围。
- **Mapping Default**：指定某公司 + 文档类型默认使用哪一个模板，并可选地覆盖部分字段（仅覆盖差异，无需复制模板）。
- **订单项创建**：默认使用所选公司/文档类型对应的默认配置；前端创建对话框允许直接选择 Single/Multiple Source。
- **订单项配置**：在订单详情页点击 “Configure Mapping” 编辑，每次保存都会校验并回写数据库。

> 老的“订单级映射文件上传/选择映射 Key”端点已废弃，调用会返回 HTTP 410。请改用新的模板 + 订单项配置流程。

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
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 启动 Frontend（Terminal 2）
```bash
cd GeminiOCR/frontend
npm run dev
```

### 访问
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 🧑‍💼 后台管理入口

- 模板管理：`http://localhost:3000/admin/mapping`
  - 创建 Mapping Template：填写主 CSV 路径、外部/内部 Join Key，按需限定公司/文档类型。
  - 配置 Mapping Default：为“公司 + 文档类型 + 模式”指定默认模板，可选添加覆盖字段。
- 订单详情页：每个订单项显示当前模式/模板来源，点击 “Configure Mapping” 可继承默认或自定义覆盖。

---

## 🐳 Docker 部署（开发/生产）

平台提供完整的 Docker 化方案与零停机部署脚本。

### 开发环境（可选）
```bash
# 启动
docker compose -f docker/docker-compose.dev.yml up -d

# 查看状态与日志
docker compose -f docker/docker-compose.dev.yml ps
docker compose -f docker/docker-compose.dev.yml logs -f
```

### 生产部署
```bash
# 蓝绿部署（推荐）
docker/deploy.sh blue-green auto     # 智能选择镜像源（Hub 优先）

# 滚动更新
docker/deploy.sh rolling auto

# 指定版本（从 Docker Hub 拉取）
DEPLOY_VERSION=v1.0.0 docker/deploy.sh blue-green hub
```

> 部署脚本会完成：预检查 → 备份 → 构建/拉取镜像 → 蓝绿/滚动部署 → 健康验证 → 清理旧资源。

### Compose 说明
- 推荐 `docker compose`（Compose v2）。
- Compose 文件中的顶层 `version:` 已弃用，已按 v2 规范兼容。

---

## 🔁 CI/CD（GitHub Actions）

完整的四阶段流水线：**功能开发** → **UAT测试** → **生产发布** → **维护回滚**

安全护栏（自动化）：
- 提交/PR 自动运行密钥扫描：Gitleaks + TruffleHog（命中即失败）
- Terraform IaC 检测：Checkov（命中阻断）

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

### 🏁 环境与审批（UAT/Prod）
- 在仓库 Settings → Environments 中新建 `uat` 与 `production` 环境，并为二者设置 Required reviewers（发布前审批点）。
- 在 AWS 中为每个环境创建 Secrets Manager 项：`sandbox/database`、`uat/database`、`prod/database`，JSON 必须含 `{"database_url": "postgresql://...:5432/document_processing_platform?sslmode=require"}`。
- 在仓库 Secrets 配置 AWS 访问（任选其一）：
  - `AWS_ROLE_TO_ASSUME`（推荐，OIDC 方式），或
  - `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`。
- 流程：
  - develop 分支：先执行 UAT 迁移（需 `uat` 审批）→ 再部署到 Staging。
  - 标记版本（tags）：先执行 Prod 迁移（需 `production` 审批）→ 再创建 Release。

### 集成测试要点
- 使用 Compose v2 启动 `db / redis / backend / frontend`
- 后端健康探针命中 `/health`，根路径 404 不视为失败
- Postgres 健康检查使用 `-d ${POSTGRES_DB}` 避免噪声日志

### 常见失败与修复
- 推送镜像被拒：确认仓库存在且已 `docker/login-action`
- SARIF 上传被拒：添加 `permissions.security-events: write`，仅在非 PR 上传
- `docker-compose` 未找到：在 CI 使用 `docker compose`
- SQLite/依赖问题：测试时用 `sqlite:////tmp/test.db`；安装 `python-multipart`

### 本地验证建议

- **后端单元测试**：
  ```bash
  cd GeminiOCR/backend
  pytest -q
  ```
- **前端类型/构建检查**：
  ```bash
  cd GeminiOCR/frontend
  npm run lint
  npm run build
  ```
- **手动验证**：
  1. 后台 `Admin → Mapping Templates` 创建模板与默认值。
  2. 新建订单、添加订单项，分别体验 Single Source 与 Multiple Source。
  3. 在订单详情中调整配置并触发 Start Mapping，确认生成的 CSV 反映最新配置。

---

## 📁 目录结构

```
KH-COURSERA/
├── GeminiOCR/            # 应用代码
│   ├── backend/          # FastAPI app
│   │   ├── app.py        # 主应用（含 WebSocket）
│   │   ├── config_loader.py # 配置加载与校验
│   │   ├── db/           # 数据库模型与连接
│   │   └── utils/        # S3/Excel/工具
│   └── frontend/         # Next.js 应用
│       └── src/app/
├── env/                  # 环境配置文件（集中管理）
│   ├── .env.example      # 模板文件
│   ├── .env.development  # 开发环境配置
│   └── .env.local        # 本地覆盖（gitignored）
├── docker/               # Docker 配置（集中管理）
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml
│   └── deploy.sh         # 零停机部署脚本
├── migrations/           # 数据库迁移文件
├── scripts/              # 数据库和部署脚本
├── terraform/            # 基础设施即代码
├── config/               # 应用配置文件
└── .github/workflows/    # CI/CD 流水线
```

---

## ⚙️ 配置

### 环境文件（集中管理）
- 项目根目录：`env/`（统一管理所有环境配置）
  - `.env.development` / `.env.staging` / `.env.production` / `.env.local (gitignored)`
  - `.env.example`：模板清单（无敏感信息）
- 兼容性：后端 config_loader.py 支持多路径自动加载
- 前端：同样使用 `env/.env.local`

运行方式：
- 本地：`cd GeminiOCR && cp env/env.example env/.env.development && <填入本地变量>`
- Docker Compose：`docker compose --env-file env/.env.development -f docker/docker-compose.dev.yml up -d`

### 示例（Sandbox）
```bash
# Backend (backend/env/.env.sandbox)
ENVIRONMENT=sandbox
PORT=8000
# 注意：仅在 backend/env/.env 中保存凭证；其他位置仅引用
# 示例（不要在文档中放真实值）
# DATABASE_URL="postgresql://HYA_OCR:<ENCODED_PASSWORD>@hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432/document_processing_platform"
S3_BUCKET_NAME=hya-ocr-sandbox
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
GEMINI_API_KEY_1=your_sandbox_gemini_key

# Frontend (frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 示例（Production）
```bash
# Backend (backend/env/.env.production)
ENVIRONMENT=production
PORT=8000
# 注意：仅在 backend/env/.env 中保存凭证；其他位置仅引用
# 示例（不要在文档中放真实值）
# DATABASE_URL="postgresql://HYA_OCR:<ENCODED_PASSWORD>@hya-ocr-instance-dev.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432/document_processing_platform"
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
S3_BUCKET_NAME=hya-ocr-production
```

**注意**
- 不要提交 `.env*` 文件，尤其是 `.env.local`；仅提交 `env.example`
- 配置优先级：环境变量 > AWS Secrets > `.env.<env>` > 默认值

## 🗄️ 数据库与环境（Aurora + 本地 Postgres）

统一由 `GeminiOCR/backend/config_loader.py` 读取数据库配置，优先级：环境变量 > AWS Secrets Manager > 配置文件。

- 开发切换（不改文件，直接导出变量）：
  - 本地：`source scripts/use-db.sh local`（`sslmode=disable`）
  - 云端：`source scripts/use-db.sh sandbox|uat|production`（注入 `DATABASE_SECRET_NAME=<env>/database`）
  - 也可直接：`export DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=...`

- 迁移（Alembic）：
  - `cd GeminiOCR/backend && pip install -r requirements.txt`
  - `bash ./scripts/manage_migrations.sh upgrade head`
  - 约定：生产/UAT依赖 Alembic；仅在 `ENVIRONMENT ∈ {development,test}` 时后端会执行 `Base.metadata.create_all` 便于本地起步。

- CI/CD 迁移（带审批）：
  - 手动：`.github/workflows/db-migrate.yml`（选择 `sandbox/uat/production/custom_url`）
  - UAT：部署到 Staging 前自动执行迁移（Environment `uat` 审批）
  - Prod：创建 Release 前自动执行迁移（Environment `production` 审批）

- Terraform（Aurora 脚手架）：
  - 目录：`terraform/modules/aurora-postgresql/` 与 `terraform/environments/{sandbox,uat,production}`
  - 变量：`region`、`vpc_id`、`subnet_ids`（私有子网）`allowed_sg_ids`（允许访问 5432 的应用 SG 列表）`secret_name`
  - 示例：
    ```hcl
    module "aurora" {
      source         = "../../modules/aurora-postgresql"
      name           = "geminiocr-sandbox"
      region         = "ap-southeast-1"
      vpc_id         = "vpc-xxxx"
      subnet_ids     = ["subnet-a","subnet-b","subnet-c"]
      allowed_sg_ids = ["sg-app"]
      secret_name    = "sandbox/database"
    }
    ```
  - 运行：
    ```bash
    cd terraform/environments/sandbox
    terraform init && terraform apply \
      -var="region=ap-southeast-1" \
      -var="vpc_id=vpc-xxxx" \
      -var='subnet_ids=["subnet-a","subnet-b","subnet-c"]' \
      -var='allowed_sg_ids=["sg-app"]'
    ```
  - 输出：`cluster_endpoint`、`secret_arn`；后端只需设置 `DATABASE_SECRET_NAME=<env>/database` 即可切换。

---

## 🔍 监控与健康
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
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
docker/deploy.sh -h
docker/deploy.sh blue-green auto 2>&1 | tee deploy.log
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
