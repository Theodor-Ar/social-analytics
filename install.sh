#!/usr/bin/env bash
set -e

echo "=== Установка системных пакетов ==="
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib python3 python3-venv python3-pip
sudo systemctl enable --now postgresql

echo "=== Настройка базы данных PostgreSQL ==="
sudo -u postgres psql -c "CREATE USER analytics_user WITH PASSWORD 'analytics_pass';" || true
sudo -u postgres psql -c "CREATE DATABASE social_analytics OWNER analytics_user;" || true

PGPASSWORD=analytics_pass psql -h localhost -U analytics_user -d social_analytics -f sql/init.sql

echo "=== Настройка виртуального окружения Python ==="
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install uv
./venv/bin/uv sync

echo "Установка успешно завершена. Для запуска выполните: ./run.sh"