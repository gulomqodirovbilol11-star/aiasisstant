@echo off
chcp 65001 > nul
echo ===================================================
echo  Telegram Shaxsiy AI Agent ishga tushirilmoqda...
echo ===================================================

if not exist ".env" (
    echo [OGOHLANTIRISH] .env fayli topilmadi. .env.example dan nusxa olinmoqda...
    copy .env.example .env
    echo Iltimos, .env faylini ochib Telegram API va Gemini API kalitlarini kiriting!
    notepad .env
    pause
    exit /b
)

if not exist "venv\Scripts\python.exe" (
    echo [MA'LUMOT] Virtual muhit yaratilmoqda...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

python main.py
pause
