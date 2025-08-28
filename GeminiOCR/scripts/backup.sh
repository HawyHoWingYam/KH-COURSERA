#!/bin/bash

# ==============================================
# GeminiOCR 自动备份脚本
# ==============================================
# 定期备份RDS数据库到S3

set -euo pipefail

# 配置
BACKUP_NAME="gemini-backup-$(date +%Y%m%d_%H%M%S)"
TEMP_DIR="/tmp/backups"
RETENTION_DAYS=30

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 创建备份目录
mkdir -p "$TEMP_DIR"

# 数据库备份
log "开始数据库备份..."

if [[ -n "${DATABASE_URL:-}" ]]; then
    # 从DATABASE_URL解析连接信息
    DB_USER=$(echo $DATABASE_URL | sed 's/.*:\/\/\([^:]*\):.*/\1/')
    DB_PASS=$(echo $DATABASE_URL | sed 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/')
    DB_HOST=$(echo $DATABASE_URL | sed 's/.*@\([^:]*\):.*/\1/')
    DB_PORT=$(echo $DATABASE_URL | sed 's/.*:\([0-9]*\)\/.*/\1/')
    DB_NAME=$(echo $DATABASE_URL | sed 's/.*\/\([^?]*\).*/\1/')
    
    # 使用pg_dump备份数据库
    PGPASSWORD="$DB_PASS" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-password \
        --verbose \
        --format=custom \
        --file="$TEMP_DIR/${BACKUP_NAME}.dump"
    
    log "数据库备份完成: ${BACKUP_NAME}.dump"
else
    log "错误: DATABASE_URL 未设置"
    exit 1
fi

# 压缩备份文件
log "压缩备份文件..."
gzip "$TEMP_DIR/${BACKUP_NAME}.dump"

# 上传到S3
log "上传备份到S3..."
if [[ -n "${AWS_S3_BACKUP_BUCKET:-}" ]]; then
    aws s3 cp \
        "$TEMP_DIR/${BACKUP_NAME}.dump.gz" \
        "s3://${AWS_S3_BACKUP_BUCKET}/database-backups/${BACKUP_NAME}.dump.gz" \
        --storage-class STANDARD_IA
    
    log "备份上传成功: s3://${AWS_S3_BACKUP_BUCKET}/database-backups/${BACKUP_NAME}.dump.gz"
else
    log "警告: AWS_S3_BACKUP_BUCKET 未设置，跳过S3上传"
fi

# 清理本地备份文件
rm -f "$TEMP_DIR/${BACKUP_NAME}.dump.gz"

# 清理旧备份 (保留指定天数的备份)
log "清理旧备份文件..."
if [[ -n "${AWS_S3_BACKUP_BUCKET:-}" ]]; then
    # 计算删除日期
    DELETE_DATE=$(date -d "${RETENTION_DAYS} days ago" '+%Y-%m-%d')
    
    # 列出并删除旧备份
    aws s3api list-objects-v2 \
        --bucket "${AWS_S3_BACKUP_BUCKET}" \
        --prefix "database-backups/" \
        --query "Contents[?LastModified<'${DELETE_DATE}'].Key" \
        --output text | \
    while read -r key; do
        if [[ -n "$key" && "$key" != "None" ]]; then
            aws s3 rm "s3://${AWS_S3_BACKUP_BUCKET}/$key"
            log "删除旧备份: $key"
        fi
    done
fi

log "备份任务完成"

# 定时运行备份的主循环
if [[ "${1:-}" == "--daemon" ]]; then
    log "启动备份守护进程，计划: ${BACKUP_SCHEDULE:-0 2 * * *}"
    
    # 安装cron作业
    echo "${BACKUP_SCHEDULE:-0 2 * * *} /app/scripts/backup.sh" > /tmp/crontab
    crontab /tmp/crontab
    
    # 启动cron守护进程
    cron -f
fi