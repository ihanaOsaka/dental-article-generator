@echo off
cd /d "%~dp0"
echo 歯科記事ジェネレーターを起動中...
python -m streamlit run app/main.py --server.headless true --browser.gatherUsageStats false
pause
