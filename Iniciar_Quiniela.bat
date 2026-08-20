@echo off
title Sistema de Reduccion de Quinielas
cd /d "%~dp0"
echo Iniciando la app... se va a abrir tu navegador en unos segundos.
echo (No cierres esta ventana mientras la uses - al cerrarla se apaga el servidor)
echo.
python -m streamlit run app.py
echo.
echo El servidor se detuvo.
pause
