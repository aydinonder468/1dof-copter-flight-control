@echo off
setlocal
title Build and Flash STM32 Flight Controller

set ARDUINO_CLI=C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe
set PROJECT_DIR=%~dp0..
set SKETCH_DIR=%PROJECT_DIR%\firmware\sensor_read_arduino
set BUILD_DIR=%PROJECT_DIR%\build_1dof_controller
set FQBN=STMicroelectronics:stm32:GenF4:pnum=BLACKPILL_F401CE,usb=CDCgen,xserial=generic,xusb=FS,upload_method=swdMethod

echo Building firmware...
"%ARDUINO_CLI%" compile --fqbn "%FQBN%" "%SKETCH_DIR%" --build-path "%BUILD_DIR%"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Flashing firmware over ST-Link/SWD...
"%ARDUINO_CLI%" upload --fqbn "%FQBN%" "%SKETCH_DIR%" --input-dir "%BUILD_DIR%"
if errorlevel 1 (
  echo Upload failed. Check ST-Link wiring and power.
  pause
  exit /b 1
)

echo.
echo Waiting for USB CDC serial port...
timeout /t 5 /nobreak >nul

for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0find_stm32_port.ps1" 2^>nul`) do set STM32_PORT=%%P

if "%STM32_PORT%"=="" (
  echo Firmware uploaded, but STM32 USB serial port was not found.
  echo Press RESET once. If it still does not appear, check USB-C data cable and BOOT0.
) else (
  echo STM32 serial port is ready: %STM32_PORT%
)

pause
