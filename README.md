# 1-DOF Copter Flight Control

Bu proje, tek serbestlik dereceli bir copter test duzenegi icin hazirlanan STM32 firmware, Python flight-controller interface ve MATLAB model/simulasyon dosyalarini icerir.

Sistem iki motorlu bir pivot kolu dengeler. STM32, GY-91 sensor kartindan aci/hiz verisini okur, PID kontrol ile sol/sag ESC PWM komutlarini uretir ve USB CDC seri port uzerinden interface uygulamasina telemetri gonderir.

## Demo Videolari

- MATLAB simulasyon animasyonu: [`media/simulation_motion.mp4`](media/simulation_motion.mp4)
- Interface ve STM32 seri telemetri demosu: [`media/interface_demo.mp4`](media/interface_demo.mp4)

## Klasor Yapisi

```text
.
|-- firmware/
|   `-- sensor_read_arduino/
|       `-- sensor_read_arduino.ino
|-- interface/
|   |-- main.py
|   |-- main_window.py
|   |-- requirements.txt
|   |-- run.bat
|   |-- run_serial.bat
|   |-- telemetry/
|   |-- utils/
|   `-- widgets/
|-- matlab/
|   |-- init_1dof_params.m
|   |-- run_pso_pid_autotune.m
|   |-- simulate_noisy_pid_response.m
|   |-- export_1dof_copter_video.m
|   `-- output/
|-- media/
|   |-- interface_demo.mp4
|   |-- simulation_motion.mp4
|   `-- images/
|-- tools/
|   |-- flash_stm32_firmware.bat
|   |-- find_stm32_port.ps1
|   |-- run_interface_auto.bat
|   `-- send_stm32_command.ps1
`-- main.m
```

## Kullanilan Donanim

- WeAct STM32F401 / BlackPill F401CE karti
- GY-91 sensor karti
  - MPU9250/MPU6500 tabanli IMU
  - BMP280/BME280 barometre
- 2 adet brushless motor
- 2 adet ESC
- 10x4.5 pervane tipi icin modellenmis motor/prop parametreleri
- ST-Link programlayici
- STM32 USB-C data kablosu
- Harici pil veya guc kaynagi
- 1-DOF pivot kol mekanigi

## STM32 - GY-91 SPI Baglantisi

| GY-91 Pin | STM32 Pin | Gorev |
| --- | --- | --- |
| V3 / 3V3 | 3.3V | Sensor beslemesi |
| GND | GND | Ortak toprak |
| SCL | PA5 | SPI1 SCK |
| SDA | PA7 | SPI1 MOSI |
| SDO / SAO | PA6 | SPI1 MISO |
| NCS | PB0 | MPU chip select |
| CSB | PB1 | BMP/BME chip select |

## Motor PWM Baglantisi

| STM32 Pin | Gorev |
| --- | --- |
| A2 / PA2 | Sol ESC sinyal |
| A3 / PA3 | Sag ESC sinyal |
| GND | ESC GND ile ortak toprak |

ESC sinyal kablosu tek basina yeterli degildir. STM32 GND ile ESC GND ortaklanmalidir.

## Gerekli Yazilimlar

### Firmware icin

- Arduino IDE veya Arduino CLI
- STM32duino / STM32 Arduino Core
- STM32CubeProgrammer
- ST-Link suruculeri

Arduino kart ayarlari:

```text
Board: Generic STM32F4 series
Board part number: BlackPill F401CE
Upload method: STM32CubeProgrammer (SWD)
USB support: CDC (generic Serial supersede USART)
USB speed: Low/Full Speed
Baud: 115200
```

### Interface icin

- Python 3.10 veya daha yeni
- PySide6
- PyOpenGL
- numpy
- pyserial

Kurulum:

```powershell
cd interface
python -m pip install -r requirements.txt
```

### MATLAB simulasyonu icin

- MATLAB
- Simulink opsiyonel; `build_1dof_simulink_model.m` icin gerekir
- Temel simulasyon ve video export icin MATLAB scriptleri yeterlidir

## Firmware Yukleme

Firmware dosyasi:

```text
firmware/sensor_read_arduino/sensor_read_arduino.ino
```

Windows uzerinde Arduino CLI ve STM32CubeProgrammer kuruluysa:

```powershell
tools\flash_stm32_firmware.bat
```

Bu script firmware'i derler, ST-Link/SWD ile STM32'ye yukler ve yukleme sonunda USB CDC COM portunu arar.

## Interface Calistirma

Mock veri ile arayuzu acmak:

```powershell
cd interface
run.bat
```

STM32 seri telemetri ile arayuzu acmak:

```powershell
interface\run_serial.bat
```

COM portunu otomatik bulup arayuzu acmak:

```powershell
tools\run_interface_auto.bat
```

Interface STM32'den gelen binary telemetri paketini `interface/telemetry/serial_telemetry_client.py` icinde cozer. Arayuz ARM/DISARM ve referans acisi komutlarini seri port uzerinden STM32'ye gonderebilir.

## Seri Komutlar

Firmware asagidaki komutlari destekler:

```text
ARM,1
ARM,0
DISARM
REF,<derece>
PID,<kp>,<ki>,<kd>
KAL,<qAngle>,<qRate>,<rAngle>,<rRate>
HOVER,<us>
IDLE,<us>
MOTOR,<left_us>,<right_us>,<ms>
STATUS
```

Ornek:

```powershell
tools\send_stm32_command.ps1 "STATUS"
```

## MATLAB Modelini Calistirma

Repo kok dizininden:

```matlab
run('main.m')
```

`main.m` su islemleri yapar:

1. MATLAB yollarini ayarlar.
2. `matlab/output/tuned_pid_gains.json` ve mevcut gain dosyalarini kullanir.
3. 1-DOF copter icin gercekci, gurultulu PID simulasyonunu calistirir.
4. `matlab/output/one_dof_copter_motion.mp4` videosunu uretir.

PSO ile yeniden PID tuning yapmak icin MATLAB icinde:

```matlab
p = init_1dof_params();
result = run_pso_pid_autotune(p);
sim = simulate_noisy_pid_response(result.gains, p);
export_1dof_copter_video(sim, p);
```

## Mevcut Kontrol Ayarlari

Firmware icindeki baslangic PID degerleri:

```text
Kp = 3.25
Ki = 0.35
Kd = 0.65
```

PWM ayarlari:

```text
minPwm = 1000 us
maxPwm = 2000 us
hoverPwm = 1300 us
armedMinPwm = 1300 us
```

Kontrol ekseni firmware'de roll ekseni olarak ayarlidir:

```cpp
#define CONTROL_AXIS_PITCH 0
```

## Guvenlik Notlari

- Pervaneler takiliyken motor testi yapmayin.
- Motor/ESC guc kaynagi yeterli akim verebilmelidir.
- STM32 GND ve ESC GND ortak olmalidir.
- Ilk testlerde mekanik aci limiti kullanin.
- ARM etmeden once sensorlerin dogru aci isareti verdigini kontrol edin.

