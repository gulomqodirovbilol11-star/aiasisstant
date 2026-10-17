#!/bin/bash
set -e

echo "==================================================="
echo " Telegram Shaxsiy AI Agent ishga tushirilmoqda..."
echo "==================================================="

if [ ! -f ".env" ]; then
    echo "[OGOHLANTIRISH] .env fayli topilmadi. .env.example dan nusxa olinmoqda..."
    cp .env.example .env
    echo "Iltimos, .env faylini tahrirlab o'z ma'lumotlaringizni kiriting!"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[MA'LUMOT] Virtual muhit yaratilmoqda..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

python3 main.py
