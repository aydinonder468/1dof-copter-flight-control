@echo off
title STM32 ESC Signal Test 1100us
echo WARNING: Remove propellers and secure the test stand.
echo Sending MOTOR,1100,1100,3000 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0send_stm32_command.ps1" -Command "MOTOR,1100,1100,3000"
pause
