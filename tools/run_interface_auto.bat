@echo off
setlocal
title Flight Controller Interface - Auto STM32 Port

for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0find_stm32_port.ps1" 2^>nul`) do set STM32_PORT=%%P

if "%STM32_PORT%"=="" (
  echo STM32 USB serial port not found.
  echo.
  echo Check:
  echo - STM32 USB-C data cable is connected
  echo - BOOT0 is not pressed
  echo - Press RESET once and wait 3 seconds
  echo.
  pause
  exit /b 1
)

echo Using STM32 port: %STM32_PORT%
cd /d "%~dp0..\interface"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 main.py --serial --serial-port %STM32_PORT% --baud 115200
) else (
  python main.py --serial --serial-port %STM32_PORT% --baud 115200
)
pause
