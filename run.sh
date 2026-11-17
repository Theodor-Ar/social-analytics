#!/usr/bin/env bash
set -e

source venv/bin/activate

echo "=== [1/2] Запуск ETL-процесса (сбор и загрузка данных) ==="
python3 etl/etl.py

echo "=== [2/2] Расчёт аналитических показателей ==="
PGPASSWORD=analytics_pass psql -h localhost -U analytics_user -d social_analytics -f sql/analytics.sql