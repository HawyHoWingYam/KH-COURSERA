# 多阶段构建 - 构建阶段 (Phase 2.2: Updated Node.js for npm security fixes)
FROM node:20-alpine AS builder

# 设置工作目录
WORKDIR /app

# 升级npm以修復系統級安全漏洞 (Phase 2.2)
RUN npm install -g npm@latest

# 复制package files
COPY GeminiOCR/frontend/package.json GeminiOCR/frontend/package-lock.json ./

# 安装依赖 (Phase 2.1 security fix: cross-spawn ^7.0.5 override)
RUN npm ci --production=false && npm cache clean --force

# 复制源代码（排除.env文件避免构建时污染）
COPY GeminiOCR/frontend/ .
RUN rm -f .env .env.local .env.*.local

# Cache bust layer - increment this to force rebuild
ARG CACHE_BUST=1
RUN echo "Cache bust: $CACHE_BUST"

# 构建应用
RUN npm run build

# 生产阶段 (Phase 2.2: Updated Node.js for npm security fixes)  
FROM node:20-alpine AS production

# 设置环境变量
ENV NODE_ENV=production

# 创建非root用户
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

# 设置工作目录
WORKDIR /app

# 复制public文件夹
COPY --from=builder /app/public ./public

# 复制构建产物
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# 切换到非root用户
USER nextjs

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1

# 暴露端口
EXPOSE 3000

# 启动命令
CMD ["node", "server.js"]