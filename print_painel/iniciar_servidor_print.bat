@echo off
title Painel NeuralBIM - prints
cd /d C:\NeuralBim\print_painel
py servidor_print.py > C:\NeuralBim\print_painel\servidor.log 2>&1
pause
