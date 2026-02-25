#!/bin/bash

# Скрипт для установки systemd сервиса Metagenerator API
# Перед запуском: отредактируйте metagenerator-api.service (User, WorkingDirectory, PATH)
set -e

echo "Устанавливаю systemd сервис Metagenerator API..."

if [ ! -f "metagenerator-api.service" ]; then
    echo "Ошибка: metagenerator-api.service не найден. Запустите скрипт из корня проекта."
    exit 1
fi

echo "Копирую service файл..."
sudo cp metagenerator-api.service /etc/systemd/system/

echo "Перезагружаю systemd daemon..."
sudo systemctl daemon-reload

echo "Включаю автозапуск сервиса..."
sudo systemctl enable metagenerator-api.service

echo "Запускаю сервис..."
sudo systemctl start metagenerator-api.service

echo "Статус сервиса:"
sudo systemctl status metagenerator-api.service --no-pager -l

echo ""
echo "Полезные команды:"
echo "   sudo systemctl status metagenerator-api   # Статус"
echo "   sudo systemctl restart metagenerator-api  # Перезапуск"
echo "   sudo systemctl stop metagenerator-api     # Остановка"
echo "   sudo journalctl -u metagenerator-api -f   # Логи"
echo ""
