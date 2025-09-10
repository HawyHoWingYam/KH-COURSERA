# 🐳 GeminiOCR Docker 部署指南

> **注意**: 对于本地开发，推荐使用 [Anaconda 环境](../CLAUDE.md#quick-start-guide)。
> 本文档主要针对 Docker 容器化部署场景。

## 📋 概述

此文档提供完整的Docker化部署解决方案，支持：
- 🏠 本地开发环境 (推荐使用 Anaconda)
- 🚀 生产环境部署
- ☁️ AWS云服务集成 (RDS + S3)
- 🔄 零停机部署策略

## 🏗️ 架构组件

### 核心服务
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │    │    Frontend     │    │    Backend      │
│  (反向代理)      │◄──►│   (Next.js)     │◄──►│   (FastAPI)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │              ┌─────────────────┐
         │                       │              │   PostgreSQL    │
         │                       │              │  (RDS/Local)    │
         │                       │              └─────────────────┘
         │                       │                       │
         │                       │              ┌─────────────────┐
         │                       │              │      Redis      │
         │                       │              │    (缓存)       │
         │                       │              └─────────────────┘
         │                       │                       │
         │                       │              ┌─────────────────┐
         │                       │              │   AWS S3        │
         │                       │              │ (文件存储)      │
         │                       └──────────────┴─────────────────┘
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目到docker-deployment-integration分支
git clone https://github.com/yourusername/GeminiOCR.git
cd GeminiOCR
git checkout docker-deployment-integration

# 复制环境变量模板
cp .env.example .env
```

### 2. 配置环境变量

编辑 `.env` 文件：

```bash
# 数据库配置
POSTGRES_USER=gemini_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=gemini_production

# AWS S3 存储 (可选)
AWS_S3_BUCKET=your-s3-bucket-name
AWS_DEFAULT_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
```

### 3. 配置后端密钥

编辑 `backend/env/.env` 文件：

```bash
# Gemini API密钥
GEMINI_API_KEY_1=your_gemini_api_key_1
GEMINI_API_KEY_2=your_gemini_api_key_2

# 其他配置...
```

## 🏠 本地开发部署

> **推荐**: 使用 [Anaconda 开发环境](../CLAUDE.md#quick-start-guide) 进行本地开发，更加轻量和快速。

### Docker 开发环境 (可选)

```bash
# 使用开发配置启动
docker-compose -f docker-compose.dev.yml up -d

# 查看服务状态
docker-compose -f docker-compose.dev.yml ps

# 查看日志
docker-compose -f docker-compose.dev.yml logs -f
```

### 访问服务

**Docker 环境:**
- **前端**: http://localhost:3000
- **后端API**: http://localhost:8000  
- **API文档**: http://localhost:8000/docs
- **数据库**: localhost:5432
- **Redis**: localhost:6379

**Anaconda 环境 (推荐):**
- **前端**: http://localhost:3000
- **后端API**: http://localhost:8001
- **API文档**: http://localhost:8001/docs

### 开发工具

```bash
# 进入开发工具容器
docker-compose -f docker-compose.dev.yml --profile tools up devtools
docker-compose -f docker-compose.dev.yml exec devtools bash

# 运行数据库检查
docker-compose -f docker-compose.dev.yml exec backend python check_db.py

# 重新初始化数据库
docker-compose -f docker-compose.dev.yml exec backend python init_db.py
```

## 🚀 生产环境部署

### 方案 1: 使用内置PostgreSQL

```bash
# 生产环境部署
./deploy.sh blue-green

# 或使用滚动更新
./deploy.sh rolling

# 查看部署状态
docker-compose ps
```

### 方案 2: 使用AWS RDS

```bash
# 配置AWS RDS连接
export AWS_RDS_DATABASE_URL="postgresql://user:pass@your-rds-endpoint:5432/dbname"

# 使用RDS配置部署
docker-compose -f docker-compose.prod.yml up -d

# 运行数据库迁移
docker-compose -f docker-compose.prod.yml run --rm db-migrate
```

## ⚙️ 部署配置选项

### docker-compose.yml (标准部署)
- 包含完整的应用栈
- 使用容器化PostgreSQL
- 适合中小型部署

### docker-compose.prod.yml (生产AWS部署)  
- 使用AWS RDS数据库
- S3文件存储
- Redis缓存
- 生产级监控

### docker-compose.dev.yml (开发环境)
- 代码热重载
- 暴露调试端口
- 开发工具容器

## 🔧 高级配置

### SSL/TLS 配置

```bash
# 创建SSL证书目录
mkdir -p ssl

# 放置证书文件
cp your-cert.pem ssl/cert.pem
cp your-key.pem ssl/key.pem

# 更新环境变量
echo "HTTPS_PORT=443" >> .env
```

### 监控和备份

```bash
# 启用监控服务
docker-compose --profile monitoring up -d

# 启用自动备份
docker-compose --profile backup up -d

# 手动备份
docker-compose exec backup /app/scripts/backup.sh
```

## 🛠️ 运维操作

### 查看服务状态

```bash
# 检查所有服务健康状态
curl http://localhost/health

# 查看详细日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx
```

### 数据库操作

```bash
# 连接数据库
docker-compose exec db psql -U gemini_user -d gemini_production

# 备份数据库
docker-compose exec db pg_dump -U gemini_user gemini_production > backup.sql

# 恢复数据库
docker-compose exec -T db psql -U gemini_user -d gemini_production < backup.sql
```

### 扩展和伸缩

```bash
# 扩展后端实例
docker-compose up -d --scale backend=3

# 扩展前端实例  
docker-compose up -d --scale frontend=2
```

## 🔄 零停机部署流程

部署脚本 `deploy.sh` 实现自动化零停机部署：

```bash
# 蓝绿部署 (推荐)
./deploy.sh blue-green

# 滚动更新
./deploy.sh rolling
```

### 部署流程

1. **预检查**: 验证环境和配置
2. **备份**: 自动备份数据库和文件
3. **构建**: 构建新的Docker镜像
4. **部署**: 蓝绿切换或滚动更新
5. **验证**: 健康检查和功能测试
6. **清理**: 清理旧资源

### 故障回滚

```bash
# 如果部署失败，脚本会自动回滚
# 也可以手动回滚到之前版本
docker-compose down
docker-compose up -d
```

## 📊 监控和日志

### 应用监控

- **健康检查**: http://localhost/health
- **Nginx状态**: http://localhost:8080/nginx_status  
- **Prometheus监控**: http://localhost:9090 (如果启用)

### 日志管理

```bash
# 查看所有日志
docker-compose logs

# 实时跟踪特定服务日志
docker-compose logs -f backend

# 查看最近的错误日志
docker-compose logs --tail=100 backend | grep ERROR
```

## 🔧 故障排除

### 常见问题

**数据库连接失败**
```bash
# 检查数据库状态
docker-compose exec db pg_isready -U gemini_user

# 查看数据库日志
docker-compose logs db
```

**文件上传失败**
```bash
# 检查S3配置
docker-compose exec backend python -c "from utils.s3_storage import get_s3_manager; print(get_s3_manager().get_health_status())"

# 检查本地存储权限
docker-compose exec backend ls -la /app/uploads
```

**WebSocket连接问题**
```bash
# 测试WebSocket连接
docker-compose exec backend python test_websocket.py localhost 8000

# 检查Nginx配置
docker-compose exec nginx nginx -t
```

### 性能优化

**资源限制调整**
```yaml
# 在docker-compose.yml中调整
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
```

**缓存配置**
```bash
# 调整Redis内存限制
docker-compose exec redis redis-cli CONFIG SET maxmemory 1gb
```

## 🛡️ 安全最佳实践

1. **密钥管理**: 使用AWS Secrets Manager或环境变量
2. **网络安全**: 配置防火墙和VPC
3. **SSL证书**: 启用HTTPS和证书自动续期
4. **访问控制**: 设置适当的用户权限
5. **定期备份**: 自动备份到安全位置
6. **监控告警**: 设置性能和安全监控

## 📞 支持和联系

如遇到问题：

1. 查看 [README.md](./README.md) 中的常见问题
2. 检查 [日志文件](#监控和日志)
3. 运行 [健康检查](#故障排除)
4. 提交 GitHub Issue

---

🎉 **恭喜！** 您现在拥有完整的Docker化部署解决方案。这套配置支持从开发到生产的完整工作流程，具备零停机部署、自动备份、监控告警等企业级功能。