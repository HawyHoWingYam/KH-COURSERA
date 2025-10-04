#!/bin/bash
set -e

echo "🚀 Backend Container Starting..."

# 等待数据库准备就绪
echo "⏳ Waiting for database to be ready..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if python -c "from db.database import engine; engine.connect()" 2>/dev/null; then
        echo "✅ Database is ready!"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "Database not ready yet (attempt $retry_count/$max_retries)..."
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "❌ Database connection timeout!"
    exit 1
fi

# 运行数据库迁移（如果存在alembic.ini）
if [ -f "alembic.ini" ]; then
    echo "🔄 Running database migrations..."
    alembic upgrade head || {
        echo "⚠️  Migration failed, but continuing startup..."
        echo "You may need to run migrations manually"
    }
    echo "✅ Migrations completed"
else
    echo "ℹ️  No alembic.ini found, skipping migrations"
    echo "ℹ️  Running init_db.py for table creation..."
    python init_db.py || {
        echo "⚠️  init_db.py failed, but continuing startup..."
    }
fi

# 启动应用
echo "🎯 Starting uvicorn server..."
exec uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
