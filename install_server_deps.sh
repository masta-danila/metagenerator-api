#!/bin/bash

# Скрипт установки зависимостей на сервере (Metagenerator API + парсер)
# Поддерживает Ubuntu/Debian и CentOS/RHEL
# Для API обязательны: Python, Redis, Chrome (для браузерного парсинга)

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Установка зависимостей для Metagenerator API ===${NC}"

# Определение ОС
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo -e "${RED}Не удалось определить операционную систему${NC}"
    exit 1
fi

echo "Операционная система: $OS"

# Установка системных пакетов
if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
    echo -e "${YELLOW}Установка пакетов для Ubuntu/Debian...${NC}"
    
    sudo apt-get update
    sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        redis-server \
        xvfb \
        wget \
        curl \
        unzip \
        fonts-liberation \
        libnss3 \
        libgbm1 \
        libxss1 \
        libasound2 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
        libx11-xcb1 \
        libxcb-dri3-0 \
        libdrm2 \
        libgbm1 \
        libxshmfence1

elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "fedora" ]]; then
    echo -e "${YELLOW}Установка пакетов для CentOS/RHEL/Fedora...${NC}"
    
    sudo yum update -y
    sudo yum install -y \
        python3 \
        python3-pip \
        redis \
        xorg-x11-server-Xvfb \
        wget \
        curl \
        unzip \
        liberation-fonts \
        nss \
        atk \
        at-spi2-atk \
        gtk3 \
        alsa-lib
else
    echo -e "${RED}Неподдерживаемая ОС: $OS${NC}"
    exit 1
fi

# Установка Chrome
echo -e "${YELLOW}Проверка наличия Google Chrome...${NC}"

if ! command -v google-chrome &> /dev/null && ! command -v google-chrome-stable &> /dev/null; then
    echo "Google Chrome не найден, устанавливаем..."
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
        sudo apt-get install -y /tmp/google-chrome.deb
        rm /tmp/google-chrome.deb
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "fedora" ]]; then
        wget -q -O /tmp/google-chrome.rpm https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
        sudo yum localinstall -y /tmp/google-chrome.rpm
        rm /tmp/google-chrome.rpm
    fi
    
    echo -e "${GREEN}Google Chrome установлен${NC}"
else
    echo -e "${GREEN}Google Chrome уже установлен${NC}"
fi

# Проверка версии Chrome
if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    echo "Версия Chrome: $CHROME_VERSION"
elif command -v google-chrome-stable &> /dev/null; then
    CHROME_VERSION=$(google-chrome-stable --version)
    echo "Версия Chrome: $CHROME_VERSION"
fi

# Redis для API (Ubuntu/Debian)
if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
    if systemctl is-active --quiet redis-server 2>/dev/null; then
        echo -e "${GREEN}Redis уже запущен${NC}"
    else
        echo -e "${YELLOW}Запуск Redis...${NC}"
        sudo systemctl enable redis-server 2>/dev/null || true
        sudo systemctl start redis-server 2>/dev/null || true
    fi
fi

echo -e "${GREEN}Все системные зависимости установлены!${NC}"
echo ""
echo -e "${YELLOW}Следующие шаги:${NC}"
echo "1. Перейдите в директорию проекта: cd /path/to/metagenerator-api"
echo "2. Создайте виртуальное окружение: python3 -m venv venv"
echo "3. Активируйте: source venv/bin/activate"
echo "4. Установите зависимости: pip install -r requirements.txt"
echo "5. Настройте .env (см. .env.example)"
echo "6. Запуск API: ./start_all.sh (остановка: ./stop_all.sh)"
