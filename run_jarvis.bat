@echo off
title Jarvis - Local Voice Assistant
color 0b
echo.
echo  +----------------------------------------------+
echo  ^|           J A R V I S                       ^|
echo  ^|    Local Voice Assistant  No LLM           ^|
echo  ^+----------------------------------------------+
echo.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python main.py %*
echo.
echo  Session ended.
pause
