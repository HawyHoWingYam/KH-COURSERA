# 🚀 完整的 Production 部署流程指南

## 工作流程概述

```
📦 Developer Push → 🏗️ GitHub Actions → 🐳 Docker Hub → 🚀 Production EC2
    to develop           Build & Push        karasho62/         Pull & Deploy
                        Sandbox Images       hya-ocr-sandbox
```

## 前置条件

### GitHub Secrets 配置
确保 GitHub repository 设置了以下 secrets：
- `DOCKER_USERNAME`: Docker Hub 用户名
- `DOCKER_PASSWORD`: Docker Hub 密码/访问令牌

### Production EC2 环境变量
```bash
# 设置 Docker Hub 拉取配置
export DOCKER_REPOSITORY="karasho62/hya-ocr-sandbox"
export DEPLOY_VERSION="latest"

# AWS 配置
export AWS_ACCESS_KEY_ID="your_aws_access_key_id"
export AWS_SECRET_ACCESS_KEY="your_aws_secret_access_key"
export AWS_DEFAULT_REGION="ap-southeast-1"
```

## 🎯 完整部署流程

### 步骤 1: 开发者推送到 develop 分支
```bash
# 本地开发完成后
git add .
git commit -m "feat: update database schema and application logic"
git push origin develop
```

### 步骤 2: GitHub Actions 自动构建 (约 15 分钟)
✅ **自动触发**:
- 构建 backend 和 frontend 镜像
- 推送到 `karasho62/hya-ocr-sandbox:backend-latest`
- 推送到 `karasho62/hya-ocr-sandbox:frontend-latest`
- 运行安全扫描和健康检查

### 步骤 3: Production EC2 部署

#### 方法 A: 完整部署（推荐）
```bash
cd /home/ubuntu/KH-COURSERA

# 拉取最新代码
git fetch origin
git checkout docker-deployment-integration
git pull origin docker-deployment-integration

# 设置环境变量
export DOCKER_REPOSITORY="karasho62/hya-ocr-sandbox"
export DEPLOY_VERSION="latest"

# 执行零停机部署（会自动拉取最新镜像）
docker/deploy.sh blue-green hub
```

#### 方法 B: 仅数据库更新
```bash
cd /home/ubuntu/KH-COURSERA

# 设置使用 sandbox 镜像
export DOCKER_REPOSITORY="karasho62/hya-ocr-sandbox"

# 仅执行数据库迁移
docker-compose -f docker/docker-compose.prod.yml run --rm db-migrate
```

## 🔧 关键配置文件

### GitHub Actions Workflow
- **文件**: `.github/workflows/ci-cd.yml`
- **触发**: push 到 `develop`, `main` 分支或标签
- **输出**: `karasho62/hya-ocr-sandbox:backend-latest`, `karasho62/hya-ocr-sandbox:frontend-latest`

### Production Docker Compose
- **文件**: `docker/docker-compose.prod.yml`
- **数据库**: `db-migrate` 服务使用 `init_db.py`
- **配置**: 连接 AWS Aurora PostgreSQL

### Deploy Script
- **文件**: `docker/deploy.sh`
- **模式**: `blue-green hub` 使用 Docker Hub 镜像
- **功能**: 零停机部署 + 自动回滚

## ✅ 验证部署成功

### 1. 检查服务状态
```bash
docker-compose -f docker/docker-compose.prod.yml ps
```

### 2. 检查数据库更新
```bash
docker-compose -f docker/docker-compose.prod.yml run --rm backend python -c "
from db.database import get_database_url
from sqlalchemy import create_engine, text
engine = create_engine(get_database_url())
with engine.connect() as conn:
    tables = conn.execute(text(\"SELECT tablename FROM pg_tables WHERE schemaname = 'public'\")).fetchall()
    print(f'✅ Database has {len(tables)} tables')
    for table in tables:
        count = conn.execute(text(f'SELECT COUNT(*) FROM {table[0]}')).scalar()
        print(f'  {table[0]}: {count} rows')
"
```

### 3. 健康检查
```bash
# 应用健康检查
curl -f http://localhost/health

# 数据库健康检查
docker-compose -f docker/docker-compose.prod.yml run --rm backend python /app/check_db.py
```

## 🚨 故障排除

### 镜像拉取失败
```bash
# 手动拉取镜像
docker pull karasho62/hya-ocr-sandbox:backend-latest
docker pull karasho62/hya-ocr-sandbox:frontend-latest
```

### 数据库连接问题
```bash
# 检查环境变量
echo $AWS_RDS_DATABASE_URL

# 测试数据库连接
docker-compose -f docker/docker-compose.prod.yml run --rm backend python -c "
from db.database import get_database_url
print('Database URL configured:', 'YES' if get_database_url() else 'NO')
"
```

### 部署回滚
```bash
# 如果部署失败，自动回滚已在 deploy.sh 中实现
# 手动回滚到上一个版本：
docker-compose -f docker/docker-compose.prod.yml down
docker-compose -f docker/docker-compose.prod.yml up -d
```

## 🎯 完整成功标准

1. ✅ GitHub Actions 构建成功（~15分钟）
2. ✅ Docker 镜像推送到 `karasho62/hya-ocr-sandbox`
3. ✅ Production EC2 成功拉取最新镜像
4. ✅ Aurora PostgreSQL 数据库 schema 更新完成
5. ✅ 所有服务健康检查通过
6. ✅ 应用功能正常（OCR, 文件上传, S3存储）

## 📞 支持

遇到问题时的检查顺序：
1. GitHub Actions 日志
2. Docker 镜像是否在 Docker Hub
3. Production EC2 网络连接
4. AWS Aurora PostgreSQL 连接
5. 应用日志：`docker-compose logs -f`