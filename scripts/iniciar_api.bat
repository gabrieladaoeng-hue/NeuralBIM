@echo off
REM Inicia a API a partir da pasta api\ deste repositorio (caminho relativo ao script).
title API - estimativa de custo BIM
cd /d "%~dp0..\api"
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe main.py
) else (
    python main.py
)
pause
