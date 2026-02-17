#!/bin/bash

# TrustFin Admin 실행 스크립트

echo "=================================================="
echo "       TrustFin Admin System Launcher"
echo "=================================================="
echo "1. Flask Admin Dashboard 실행 (Port 5001)"
echo "2. Streamlit Data App 실행 (Port 8501)"
echo "3. 종료"
echo "=================================================="
read -p "실행할 모드를 선택하세요 (1/2/3): " mode

if [ "$mode" == "1" ]; then
    echo "Starting Flask Admin Dashboard..."
    # Flask 앱 실행
    python admin_flask.py
elif [ "$mode" == "2" ]; then
    echo "Starting Streamlit Application..."
    # Streamlit 앱 실행
    streamlit run admin_app.py
elif [ "$mode" == "3" ]; then
    echo "종료합니다."
    exit 0
else
    echo "잘못된 선택입니다."
    exit 1
fi