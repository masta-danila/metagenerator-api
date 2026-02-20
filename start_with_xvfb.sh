#!/bin/bash

# Скрипт запуска парсера с виртуальным дисплеем (Xvfb)
# Автоматически находит свободный номер дисплея во избежание конфликтов

set -e

# Цвета для логов
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Директория проекта (абсолютный путь к директории со скриптом)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${GREEN}=== Запуск SEO Tools Parser ===${NC}"
echo "Директория проекта: $PROJECT_DIR"

# Проверка наличия venv
if [ ! -d "venv" ]; then
    echo -e "${RED}Ошибка: виртуальное окружение не найдено${NC}"
    echo "Создайте виртуальное окружение: python3 -m venv venv"
    exit 1
fi

# Активация виртуального окружения
source venv/bin/activate

# Проверка наличия Xvfb
if ! command -v Xvfb &> /dev/null; then
    echo -e "${RED}Ошибка: Xvfb не установлен${NC}"
    echo "Установите Xvfb:"
    echo "  Ubuntu/Debian: sudo apt-get install xvfb"
    echo "  CentOS/RHEL: sudo yum install xorg-x11-server-Xvfb"
    exit 1
fi

# Функция поиска свободного дисплея
find_free_display() {
    local display=99
    while [ $display -lt 200 ]; do
        if [ ! -e "/tmp/.X${display}-lock" ]; then
            echo $display
            return 0
        fi
        display=$((display + 1))
    done
    echo -e "${RED}Ошибка: не найден свободный дисплей${NC}"
    exit 1
}

# Находим свободный дисплей
DISPLAY_NUM=$(find_free_display)
export DISPLAY=:${DISPLAY_NUM}

echo -e "${YELLOW}Используется дисплей: :${DISPLAY_NUM}${NC}"

# Запуск Xvfb в фоне
echo "Запуск Xvfb..."
Xvfb :${DISPLAY_NUM} -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Проверка что Xvfb запустился
sleep 2
if ! ps -p $XVFB_PID > /dev/null; then
    echo -e "${RED}Ошибка: не удалось запустить Xvfb${NC}"
    exit 1
fi

echo -e "${GREEN}Xvfb запущен (PID: $XVFB_PID)${NC}"

# Функция очистки при завершении
cleanup() {
    echo -e "\n${YELLOW}Завершение работы...${NC}"
    if ps -p $XVFB_PID > /dev/null 2>&1; then
        echo "Остановка Xvfb (PID: $XVFB_PID)..."
        kill $XVFB_PID 2>/dev/null || true
        wait $XVFB_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Очистка завершена${NC}"
}

# Ловушка для корректного завершения
trap cleanup EXIT INT TERM

# Запуск Python скрипта
echo -e "${GREEN}Запуск парсера...${NC}"
echo "----------------------------------------"

python main.py "$@"

EXIT_CODE=$?

echo "----------------------------------------"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Парсер завершен успешно${NC}"
else
    echo -e "${RED}Парсер завершен с ошибкой (код: $EXIT_CODE)${NC}"
fi

exit $EXIT_CODE
