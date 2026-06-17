param(
    [Parameter(Mandatory = $true)]
    [string]$Command,

    [int]$StartupDelayMs = 4200,

    [int]$ResponseWindowMs = 1500
)

$port = & "$PSScriptRoot\find_stm32_port.ps1" 2>$null
if (-not $port) {
    Write-Error 'STM32 USB CDC serial port was not found.'
    exit 1
}

$serial = New-Object System.IO.Ports.SerialPort($port.Trim(), 115200, 'None', 8, 'One')
$serial.DtrEnable = $true
$serial.RtsEnable = $true
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000

try {
    $serial.Open()
    Start-Sleep -Milliseconds $StartupDelayMs
    $serial.DiscardInBuffer()
    $serial.WriteLine($Command)
    Write-Output "Sent to $($port.Trim()): $Command"

    $deadline = (Get-Date).AddMilliseconds($ResponseWindowMs)
    while ((Get-Date) -lt $deadline) {
        try {
            $line = $serial.ReadLine()
            if ($line) {
                $cleanLine = $line.Trim()
                if ($cleanLine -match '^(OK|ERR|STATUS),') {
                    Write-Output $cleanLine
                    break
                }
            }
        } catch [System.TimeoutException] {
        }
    }
} finally {
    if ($serial.IsOpen) {
        $serial.Close()
    }
}
