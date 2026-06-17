$port = Get-CimInstance Win32_SerialPort |
    Where-Object { $_.PNPDeviceID -match 'VID_0483&PID_5740' } |
    Select-Object -First 1 -ExpandProperty DeviceID

if (-not $port) {
    Write-Error 'STM32 USB CDC serial port was not found. Check USB-C data cable, BOOT0 not pressed, and press RESET.'
    exit 1
}

Write-Output $port
