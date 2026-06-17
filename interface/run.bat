@echo off
title Flight Controller Interface - PFD
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 main.py %*
) else (
  python main.py %*
)
pause
