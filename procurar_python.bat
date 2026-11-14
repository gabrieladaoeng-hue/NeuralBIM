@echo off
cd /d C:\NeuralBim\api
echo inicio %date% %time% > C:\NeuralBim\api_start.log
py -0p >> C:\NeuralBim\api_start.log 2>&1
where /r C:\Users\GABRI uvicorn.exe >> C:\NeuralBim\api_start.log 2>&1
echo fim >> C:\NeuralBim\api_start.log
