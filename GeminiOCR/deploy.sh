#!/bin/bash

# ==============================================
# GeminiOCR 零停机部署脚本
# ==============================================
# 此脚本实现蓝绿部署策略，确保服务持续可用

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
PROJECT_NAME="geminiocr"
COMPOSE_FILE="docker-compose.yml"
BACKUP_DIR="./backups"
MAX_DEPLOY_TIME=600  # 10分钟超时
HEALTH_CHECK_RETRIES=30
HEALTH_CHECK_INTERVAL=10

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查必要的工具
check_prerequisites() {
    log_info "检查部署前置条件..."
    
    # 检查Docker和Docker Compose
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    
    # 检查Git (用于获取版本信息)
    if ! command -v git &> /dev/null; then
        log_warning "Git 未安装，无法获取版本信息"
    fi
    
    # 检查配置文件
    if [[ ! -f ".env" ]]; then
        log_error ".env 文件不存在，请从 .env.example 复制并配置"
        exit 1
    fi
    
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        log_error "Docker Compose 文件 $COMPOSE_FILE 不存在"
        exit 1
    fi
    
    log_success "前置条件检查完成"
}

# 创建备份
create_backup() {
    log_info "创建部署前备份..."
    
    # 创建备份目录
    mkdir -p "$BACKUP_DIR"
    
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_name="backup_${timestamp}"
    
    # 备份数据库
    log_info "备份数据库..."
    docker-compose exec -T db pg_dump -U "${POSTGRES_USER:-gemini_user}" "${POSTGRES_DB:-gemini_production}" > "${BACKUP_DIR}/db_${backup_name}.sql"
    
    # 备份上传文件 (如果使用本地存储)
    if [[ -d "./uploads" ]]; then
        log_info "备份上传文件..."
        tar -czf "${BACKUP_DIR}/uploads_${backup_name}.tar.gz" -C ./uploads .
    fi
    
    # 压缩备份文件
    tar -czf "${BACKUP_DIR}/${backup_name}.tar.gz" "${BACKUP_DIR}/db_${backup_name}.sql" "${BACKUP_DIR}/uploads_${backup_name}.tar.gz" 2>/dev/null || true
    
    # 清理临时文件
    rm -f "${BACKUP_DIR}/db_${backup_name}.sql" "${BACKUP_DIR}/uploads_${backup_name}.tar.gz" 2>/dev/null || true
    
    log_success "备份完成: ${BACKUP_DIR}/${backup_name}.tar.gz"
    echo "$backup_name"
}

# 健康检查
health_check() {
    local service=$1
    local url=$2
    local retries=${3:-$HEALTH_CHECK_RETRIES}
    
    log_info "检查 $service 健康状态..."
    
    for i in $(seq 1 $retries); do
        if curl -f -s "$url" > /dev/null 2>&1; then
            log_success "$service 健康检查通过"
            return 0
        fi
        
        log_info "健康检查 $i/$retries 失败，等待 $HEALTH_CHECK_INTERVAL 秒后重试..."
        sleep $HEALTH_CHECK_INTERVAL
    done
    
    log_error "$service 健康检查失败"
    return 1
}

# 构建或拉取镜像
build_or_pull_images() {
    local image_source=${1:-"local"}  # local, hub, or auto
    
    if [[ "$image_source" == "hub" ]]; then
        log_info "从 Docker Hub 拉取镜像..."
        pull_images_from_hub
    elif [[ "$image_source" == "auto" ]]; then
        log_info "自动选择镜像源..."
        if check_hub_images_available; then
            log_info "Docker Hub 镜像可用，使用远程镜像"
            pull_images_from_hub
        else
            log_info "Docker Hub 镜像不可用，本地构建"
            build_images_locally
        fi
    else
        log_info "本地构建 Docker 镜像..."
        build_images_locally
    fi
}

# 从 Docker Hub 拉取镜像
pull_images_from_hub() {
    local version=${DEPLOY_VERSION:-"latest"}
    local repository=${DOCKER_REPOSITORY:-"karash062/hya-ocr-sandbox"}
    
    log_info "拉取版本: $version"
    
    # 拉取后端镜像
    log_info "拉取后端镜像..."
    docker pull "${repository}-backend:${version}" || {
        log_error "拉取后端镜像失败"
        return 1
    }
    
    # 拉取前端镜像
    log_info "拉取前端镜像..."
    docker pull "${repository}-frontend:${version}" || {
        log_error "拉取前端镜像失败"
        return 1
    }
    
    # 重新标记为本地使用的标签
    docker tag "${repository}-backend:${version}" "geminiocr-backend:latest"
    docker tag "${repository}-frontend:${version}" "geminiocr-frontend:latest"
    
    log_success "镜像拉取完成"
}

# 检查 Docker Hub 镜像是否可用
check_hub_images_available() {
    local version=${DEPLOY_VERSION:-"latest"}
    local repository=${DOCKER_REPOSITORY:-"karash062/hya-ocr-sandbox"}
    
    log_info "检查 Docker Hub 镜像可用性..."
    
    # 检查后端镜像
    if ! docker manifest inspect "${repository}-backend:${version}" > /dev/null 2>&1; then
        log_warning "后端镜像 ${repository}-backend:${version} 不存在"
        return 1
    fi
    
    # 检查前端镜像
    if ! docker manifest inspect "${repository}-frontend:${version}" > /dev/null 2>&1; then
        log_warning "前端镜像 ${repository}-frontend:${version} 不存在"
        return 1
    fi
    
    log_success "Docker Hub 镜像检查通过"
    return 0
}

# 本地构建镜像（原有逻辑）
build_images_locally() {
    log_info "本地构建 Docker 镜像..."
    
    # 获取Git版本信息
    local git_commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    local git_branch=$(git branch --show-current 2>/dev/null || echo "unknown")
    
    # 构建镜像并标记版本
    docker-compose build \
        --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
        --build-arg VCS_REF=$git_commit \
        --build-arg VERSION=$git_branch \
        --parallel
    
    log_success "本地镜像构建完成"
}

# 蓝绿部署
blue_green_deploy() {
    log_info "开始蓝绿部署..."
    
    # 检查当前运行的服务
    local current_services=$(docker-compose ps --services --filter "status=running")
    
    if [[ -z "$current_services" ]]; then
        log_info "首次部署，直接启动服务..."
        docker-compose up -d
    else
        log_info "执行蓝绿部署..."
        
        # 创建新的服务实例 (绿色环境)
        log_info "启动新的服务实例..."
        docker-compose up -d --no-deps --scale backend=2 --scale frontend=2 backend frontend
        
        # 等待新实例启动
        sleep 30
        
        # 健康检查新实例
        if ! health_check "Backend" "http://localhost:8000/health"; then
            log_error "新后端实例健康检查失败，回滚部署"
            rollback_deployment
            return 1
        fi
        
        # 逐步切换流量
        log_info "切换流量到新实例..."
        
        # 重启Nginx以识别新的后端实例
        docker-compose restart nginx
        
        # 等待流量切换完成
        sleep 30
        
        # 停止旧实例
        log_info "停止旧实例..."
        docker-compose up -d --scale backend=1 --scale frontend=1
        
        # 清理旧的未使用镜像
        docker image prune -f
    fi
    
    log_success "蓝绿部署完成"
}

# 标准滚动更新部署
rolling_update_deploy() {
    log_info "开始滚动更新部署..."
    
    # 逐个更新服务
    local services=("backend" "frontend")
    
    for service in "${services[@]}"; do
        log_info "更新服务: $service"
        
        # 创建新的服务实例
        docker-compose up -d --no-deps --scale $service=2 $service
        
        # 等待新实例启动
        sleep 20
        
        # 健康检查
        local health_url="http://localhost:8000/health"
        if [[ "$service" == "frontend" ]]; then
            health_url="http://localhost:3000/"
        fi
        
        if ! health_check "$service" "$health_url" 10; then
            log_error "$service 健康检查失败，停止部署"
            return 1
        fi
        
        # 移除旧实例
        docker-compose up -d --scale $service=1 $service
        
        log_success "$service 更新完成"
    done
    
    log_success "滚动更新完成"
}

# 回滚部署
rollback_deployment() {
    log_warning "开始回滚部署..."
    
    # 停止所有服务
    docker-compose down
    
    # 恢复到之前的版本 (这需要版本标记支持)
    # 这里简化为重新启动服务
    docker-compose up -d
    
    log_warning "部署已回滚"
}

# 部署后验证
post_deploy_validation() {
    log_info "执行部署后验证..."
    
    # 检查所有服务健康状态
    local services=(
        "http://localhost/health:Backend"
        "http://localhost/:Frontend"  
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r url service_name <<< "$service_info"
        if ! health_check "$service_name" "$url" 5; then
            log_error "部署后验证失败: $service_name"
            return 1
        fi
    done
    
    # 执行数据库健康检查
    log_info "执行数据库健康检查..."
    if ! docker-compose exec backend python /app/check_db.py; then
        log_error "数据库健康检查失败"
        return 1
    fi
    
    log_success "部署后验证通过"
}

# 清理旧资源
cleanup_old_resources() {
    log_info "清理旧资源..."
    
    # 清理未使用的镜像
    docker image prune -f
    
    # 清理未使用的容器
    docker container prune -f
    
    # 清理旧的备份文件 (保留最近7个)
    if [[ -d "$BACKUP_DIR" ]]; then
        find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete 2>/dev/null || true
    fi
    
    log_success "资源清理完成"
}

# 显示部署状态
show_deployment_status() {
    log_info "部署状态概览:"
    echo "=========================="
    
    # 显示服务状态
    docker-compose ps
    
    echo ""
    log_info "服务健康检查:"
    
    # 检查各服务健康状态
    local services=(
        "http://localhost/health:系统健康"
        "http://localhost/:前端访问"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r url description <<< "$service_info"
        if curl -f -s "$url" > /dev/null 2>&1; then
            log_success "$description: ✅ 正常"
        else
            log_error "$description: ❌ 异常"
        fi
    done
    
    echo "=========================="
}

# 主部署函数
main() {
    local deployment_type=${1:-"blue-green"}
    local image_source=${2:-"auto"}
    local start_time=$(date +%s)
    
    log_info "开始 GeminiOCR 零停机部署 (策略: $deployment_type, 镜像源: $image_source)"
    
    # 设置超时
    timeout $MAX_DEPLOY_TIME bash -c '
        # 执行部署步骤
        check_prerequisites
        
        # 创建备份
        backup_name=$(create_backup)
        echo "BACKUP_NAME=$backup_name" > /tmp/deploy_backup.env
        
        # 构建或拉取镜像
        build_or_pull_images "$image_source"
        
        # 根据策略执行部署
        case "'$deployment_type'" in
            "blue-green")
                blue_green_deploy
                ;;
            "rolling")
                rolling_update_deploy
                ;;
            *)
                log_error "未知的部署策略: '$deployment_type'"
                exit 1
                ;;
        esac
        
        # 部署后验证
        post_deploy_validation
        
        # 清理旧资源
        cleanup_old_resources
    ' || {
        log_error "部署超时或失败，尝试回滚..."
        rollback_deployment
        exit 1
    }
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "部署完成! 耗时: ${duration}秒"
    
    # 显示部署状态
    show_deployment_status
    
    log_info "部署日志和监控:"
    echo "  - 应用访问: http://localhost"
    echo "  - 健康检查: http://localhost/health" 
    echo "  - 查看日志: docker-compose logs -f"
    echo "  - 监控服务: docker-compose ps"
}

# 脚本用法说明
usage() {
    echo "GeminiOCR 零停机部署脚本"
    echo ""
    echo "用法: $0 [部署策略] [镜像源]"
    echo ""
    echo "部署策略:"
    echo "  blue-green  蓝绿部署 (默认)"
    echo "  rolling     滚动更新"
    echo ""
    echo "镜像源:"
    echo "  auto        自动选择 (默认) - 优先使用 Docker Hub，失败时本地构建"
    echo "  hub         强制从 Docker Hub 拉取"
    echo "  local       强制本地构建"
    echo ""
    echo "环境变量:"
    echo "  DEPLOY_VERSION       指定要部署的版本 (默认: latest)"
    echo "  DOCKER_REPOSITORY    Docker Hub 仓库名 (默认: karash062/hya-ocr-sandbox)"
    echo ""
    echo "示例:"
    echo "  $0                           # 蓝绿部署，自动选择镜像源"
    echo "  $0 blue-green auto           # 明确指定蓝绿部署和自动镜像源"
    echo "  $0 rolling hub               # 滚动更新，从 Docker Hub 拉取"
    echo "  $0 blue-green local          # 蓝绿部署，本地构建"
    echo "  DEPLOY_VERSION=v1.0.0 $0     # 部署指定版本"
    echo ""
}

# 处理命令行参数
case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    blue-green|rolling|"")
        # 验证镜像源参数
        case "${2:-auto}" in
            auto|hub|local|"")
                main "${1:-blue-green}" "${2:-auto}"
                ;;
            *)
                log_error "无效的镜像源: $2"
                usage
                exit 1
                ;;
        esac
        ;;
    *)
        log_error "无效的部署策略: $1"
        usage
        exit 1
        ;;
esac