@echo off
title NeuralBIM API
cd /d C:\NeuralBim\api
echo inicio %date% %time% > C:\NeuralBim\api_start.log
where python >> C:\NeuralBim\api_start.log 2>&1
where py >> C:\NeuralBim\api_start.log 2>&1
python main.py >> C:\NeuralBim\api_start.log 2>&1
if errorlevel 1 py main.py >> C:\NeuralBim\api_start.log 2>&1
pause
