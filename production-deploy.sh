#!/bin/bash

# ==============================================
# GeminiOCR Production 一键部署脚本
# ==============================================

set -euo pipefail

# 配置
DOCKER_REPOSITORY="${DOCKER_REPOSITORY:-karasho62/hya-ocr-sandbox}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 步骤1: Pull Docker镜像
deploy_step_1_pull_images() {
    log_info "步骤1: 拉取Docker镜像..."

    docker pull ${DOCKER_REPOSITORY}:backend-latest
    docker pull ${DOCKER_REPOSITORY}:frontend-latest

    log_success "Docker镜像拉取完成"
}

# 步骤2: 数据库迁移
deploy_step_2_database_migration() {
    log_info "步骤2: 执行数据库迁移..."

    # 切换到生产环境
    python scripts/switch_db_env.py --env production

    # 测试数据库连接
    log_info "测试数据库连接..."
    python scripts/switch_db_env.py --test

    # 检查迁移状态
    log_info "检查当前迁移状态..."
    python scripts/manage_migrations.py --env production status

    # 应用迁移
    log_info "应用数据库迁移..."
    python scripts/manage_migrations.py --env production upgrade

    log_success "数据库迁移完成"
}

# 步骤3: 零停机部署
deploy_step_3_zero_downtime_deploy() {
    log_info "步骤3: 执行零停机部署..."

    # 设置环境变量
    export DOCKER_REPOSITORY=${DOCKER_REPOSITORY}
    export ENVIRONMENT=${ENVIRONMENT}

    # 执行蓝绿部署
    ./docker/deploy.sh blue-green hub

    log_success "零停机部署完成"
}

# 步骤4: 验证部署
deploy_step_4_verify_deployment() {
    log_info "步骤4: 验证部署成功..."

    # 等待服务启动
    sleep 30

    # 检查容器状态
    log_info "检查容器状态..."
    docker compose ps

    # 健康检查
    log_info "执行健康检查..."

    # Backend健康检查
    for i in {1..5}; do
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            log_success "Backend健康检查通过"
            break
        else
            log_warning "Backend健康检查失败，重试中... ($i/5)"
            sleep 10
        fi
    done

    # Frontend健康检查
    for i in {1..5}; do
        if curl -f http://localhost:3000/ >/dev/null 2>&1; then
            log_success "Frontend健康检查通过"
            break
        else
            log_warning "Frontend健康检查失败，重试中... ($i/5)"
            sleep 10
        fi
    done

    # 检查数据库连接
    log_info "检查数据库连接..."
    cd GeminiOCR/backend
    python check_db.py
    cd ../..

    log_success "部署验证完成"
}

# 主部署流程
main() {
    log_info "开始GeminiOCR Production部署..."
    log_info "Docker Repository: ${DOCKER_REPOSITORY}"
    log_info "Environment: ${ENVIRONMENT}"
    echo

    # 执行部署步骤
    deploy_step_1_pull_images
    echo

    deploy_step_2_database_migration
    echo

    deploy_step_3_zero_downtime_deploy
    echo

    deploy_step_4_verify_deployment
    echo

    log_success "🎉 GeminiOCR Production部署成功完成！"
    echo
    log_info "访问地址:"
    log_info "  Backend API: http://18.142.68.48:8000"
    log_info "  API文档: http://18.142.68.48:8000/docs"
    log_info "  Frontend: http://18.142.68.48:3000"
    echo
    log_info "监控命令:"
    log_info "  查看日志: docker compose logs -f"
    log_info "  检查状态: docker compose ps"
    log_info "  健康检查: curl -f http://localhost:8000/health"
}

# 错误处理
trap 'log_error "部署过程中发生错误，请检查日志"; exit 1' ERR

# 执行主流程
main "$@"