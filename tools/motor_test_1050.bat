@echo off
title STM32 ESC Signal Test 1050us
echo WARNING: Remove propellers and secure the test stand.
echo Sending MOTOR,1050,1050,3000 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0send_stm32_command.ps1" -Command "MOTOR,1050,1050,3000"
pause
