#include <Arduino.h>
#include <SPI.h>
#include <Servo.h>
#include <ctype.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

// GY-91 SPI wiring:
// SCL  -> PA5  / SPI1 SCK
// SDO  -> PA6  / SPI1 MISO
// SDA  -> PA7  / SPI1 MOSI
// NCS  -> PB0  / MPU9250 chip select
// CSB  -> PB1  / BMP280 chip select
//
// 1-DOF motor outputs:
// A2 / PA2 -> left motor PWM
// A3 / PA3 -> right motor PWM
#define SPI_SCK_PIN PA5
#define SPI_MISO_PIN PA6
#define SPI_MOSI_PIN PA7
#define MPU_CS_PIN PB0
#define BMP_CS_PIN PB1
#define LEFT_PWM_PIN PA2
#define RIGHT_PWM_PIN PA3

#define SERIAL_BAUD 115200
#define TELEMETRY_HZ 30
#define CONTROL_HZ 100

// The real 1-DOF rig balances left/right, so use roll as the control axis.
// Set this to 1 only for a front/back pitch rig.
#define CONTROL_AXIS_PITCH 0

// If the angle sign or motor correction is reversed on the real rig, change
// one of these from 1.0f to -1.0f and recompile.
#define CONTROL_SIGN 1.0f
#define MOTOR_MIX_SIGN 1.0f

Servo leftMotor;
Servo rightMotor;

static SPISettings spiSlow(1000000, MSBFIRST, SPI_MODE0);
static SPISettings spiFast(8000000, MSBFIRST, SPI_MODE0);

struct ImuData {
  float ax_g, ay_g, az_g;
  float gx_dps, gy_dps, gz_dps;
  float mx_uT, my_uT, mz_uT;
  float temp_c;
};

struct Bmp280Calib {
  uint16_t dig_T1;
  int16_t dig_T2;
  int16_t dig_T3;
  uint16_t dig_P1;
  int16_t dig_P2;
  int16_t dig_P3;
  int16_t dig_P4;
  int16_t dig_P5;
  int16_t dig_P6;
  int16_t dig_P7;
  int16_t dig_P8;
  int16_t dig_P9;
  int32_t t_fine;
};

struct BaroData {
  float temp_c;
  float pressure_pa;
  float altitude_m;
};

struct ControlState {
  float reference_deg;
  float angle_deg;
  float rate_dps;
  float error_deg;
  float integral_error;
  float filtered_rate_dps;
  float u_diff_us;
  float pwm_left_us;
  float pwm_right_us;
  bool armed;
  bool safety_latched;
};

struct __attribute__((packed)) TelemetryPacketV2 {
  uint8_t sync0;
  uint8_t sync1;
  uint8_t version;
  uint8_t flags;
  uint32_t time_ms;
  float roll_deg;
  float pitch_deg;
  float heading_deg;
  float altitude_ft;
  float vertical_speed_fpm;
  float control_ref_deg;
  float control_angle_deg;
  float control_rate_dps;
  float control_error_deg;
  float control_u_diff_us;
  float pwm_left_us;
  float pwm_right_us;
  float ax_g;
  float ay_g;
  float az_g;
  float gx_dps;
  float gy_dps;
  float gz_dps;
  float pressure_pa;
  float imu_temp_c;
  float bmp_temp_c;
  uint8_t checksum;
};

struct PidGains {
  float Kp;
  float Ki;
  float Kd;
};

struct ObserverState {
  float theta_rad;
  float theta_dot_rad_s;
  float omega_left_rad_s;
  float omega_right_rad_s;
  float p00;
  float p01;
  float p10;
  float p11;
  bool initialized;
};

static bool mpuOk = false;
static bool bmpOk = false;
static float yawDeg = 0.0f;
static float lastAltitudeFt = NAN;
static float filteredVerticalSpeedFpm = 0.0f;
static uint32_t lastTelemetryMs = 0;
static uint32_t lastYawMs = 0;
static uint32_t lastAltitudeSampleMs = 0;
static uint32_t lastControlUs = 0;

static Bmp280Calib bmpCal;

// Baseline gains from MATLAB tuning, adjusted on the real rig for faster response.
static PidGains gains = {
  3.25000000f, // Kp, us/deg
  0.35000000f, // Ki, us/(deg*s)
  0.65000000f  // Kd, us/(deg/s)
};

static const float Ts = 1.0f / CONTROL_HZ;
static const float degToRad = 0.01745329252f;
static const float radToDeg = 57.29577951f;
static const float derivativeTau = 0.035f;
static const float antiWindupTau = 0.18f;
static const float integratorLimit = 120.0f;
static const float maxSafeAngleDeg = 35.0f;
static float kalmanQAngle = 0.03f; // deg, process noise for angle per update
static float kalmanQRate = 1.50f;  // deg/s, process noise for rate per update
static float kalmanRAngle = 2.00f; // deg, angle measurement noise
static float kalmanRRate = 10.0f;  // deg/s, gyro measurement noise
static const float plantArmLeftM = 0.25f;
static const float plantArmRightM = 0.25f;
static const float plantInertia = 0.018f;
static const float plantDamping = 0.012f;
static const float plantGravity = 0.040f;
static const float plantKf = 1.85e-5f;
static const float plantTauMotor = 0.055f;
static const float plantMaxOmega = 820.0f * 11.1f * 6.28318531f / 60.0f * 0.82f;
static const int minPwm = 1000;
static const int maxPwm = 2000;
static int hoverPwm = 1300;
static int armedMinPwm = 1300;
static const int maxDiffPwm = 350;
static const float pwmSlewRate = 900.0f; // us/s
static const int pwmResolution = 1;
static const int motorTestMaxPwm = 1500;

static ControlState control = {
  0.0f,  // reference_deg, keep level by default
  NAN,
  NAN,
  0.0f,
  0.0f,
  0.0f,
  0.0f,
  (float)minPwm,
  (float)minPwm,
  false,
  false
};

static ObserverState observer = {
  0.0f,
  0.0f,
  0.0f,
  0.0f,
  0.0f,
  0.0f,
  0.0f,
  0.0f,
  false
};

static char usbCommandBuffer[96];
static size_t usbCommandLen = 0;
static bool motorOverrideActive = false;
static uint32_t motorOverrideUntilMs = 0;
static int motorOverrideLeftUs = minPwm;
static int motorOverrideRightUs = minPwm;

static float clampFloat(float value, float low, float high) {
  if (value < low) return low;
  if (value > high) return high;
  return value;
}

static int clampInt(int value, int low, int high) {
  if (value < low) return low;
  if (value > high) return high;
  return value;
}

static void csHigh() {
  digitalWrite(MPU_CS_PIN, HIGH);
  digitalWrite(BMP_CS_PIN, HIGH);
}

static uint8_t spiReadReg(uint8_t csPin, uint8_t reg) {
  SPI.beginTransaction(spiFast);
  digitalWrite(csPin, LOW);
  SPI.transfer(reg | 0x80);
  uint8_t value = SPI.transfer(0x00);
  digitalWrite(csPin, HIGH);
  SPI.endTransaction();
  return value;
}

static void spiReadRegs(uint8_t csPin, uint8_t reg, uint8_t *buf, size_t len) {
  SPI.beginTransaction(spiFast);
  digitalWrite(csPin, LOW);
  SPI.transfer(reg | 0x80);
  for (size_t i = 0; i < len; ++i) {
    buf[i] = SPI.transfer(0x00);
  }
  digitalWrite(csPin, HIGH);
  SPI.endTransaction();
}

static void spiWriteReg(uint8_t csPin, uint8_t reg, uint8_t value) {
  SPI.beginTransaction(spiSlow);
  digitalWrite(csPin, LOW);
  SPI.transfer(reg & 0x7F);
  SPI.transfer(value);
  digitalWrite(csPin, HIGH);
  SPI.endTransaction();
  delayMicroseconds(10);
}

static int16_t be16(const uint8_t *p) {
  return (int16_t)((p[0] << 8) | p[1]);
}

static uint16_t leu16(const uint8_t *p) {
  return (uint16_t)(p[0] | (p[1] << 8));
}

static int16_t les16(const uint8_t *p) {
  return (int16_t)leu16(p);
}

static bool initMpu() {
  uint8_t whoBefore = spiReadReg(MPU_CS_PIN, 0x75);
  Serial.print("MPU WHO_AM_I before init: 0x");
  Serial.println(whoBefore, HEX);

  spiWriteReg(MPU_CS_PIN, 0x6B, 0x80); // PWR_MGMT_1 reset
  delay(120);
  spiWriteReg(MPU_CS_PIN, 0x6B, 0x01); // PLL clock
  delay(10);
  spiWriteReg(MPU_CS_PIN, 0x6A, 0x10); // Disable MPU I2C interface for SPI mode
  delay(10);
  spiWriteReg(MPU_CS_PIN, 0x1A, 0x03); // Gyro DLPF
  spiWriteReg(MPU_CS_PIN, 0x1B, 0x00); // Gyro +/-250 dps
  spiWriteReg(MPU_CS_PIN, 0x1C, 0x00); // Accel +/-2 g
  spiWriteReg(MPU_CS_PIN, 0x1D, 0x03); // Accel DLPF

  uint8_t whoAfter = spiReadReg(MPU_CS_PIN, 0x75);
  Serial.print("MPU WHO_AM_I after init: 0x");
  Serial.println(whoAfter, HEX);

  // MPU6500 often returns 0x70, MPU9250 returns 0x71, MPU9255 returns 0x73.
  return whoAfter == 0x70 || whoAfter == 0x71 || whoAfter == 0x73;
}

static bool readMpu(ImuData &out) {
  uint8_t raw[14] = {0};
  spiReadRegs(MPU_CS_PIN, 0x3B, raw, sizeof(raw));

  int16_t ax = be16(&raw[0]);
  int16_t ay = be16(&raw[2]);
  int16_t az = be16(&raw[4]);
  int16_t temp = be16(&raw[6]);
  int16_t gx = be16(&raw[8]);
  int16_t gy = be16(&raw[10]);
  int16_t gz = be16(&raw[12]);

  if (ax == 0 && ay == 0 && az == 0 && gx == 0 && gy == 0 && gz == 0) {
    return false;
  }

  out.ax_g = ax / 16384.0f;
  out.ay_g = ay / 16384.0f;
  out.az_g = az / 16384.0f;
  out.temp_c = (temp / 333.87f) + 21.0f;
  out.gx_dps = gx / 131.0f;
  out.gy_dps = gy / 131.0f;
  out.gz_dps = gz / 131.0f;

  // AK8963 magnetometer is behind the MPU internal I2C master in SPI mode.
  out.mx_uT = NAN;
  out.my_uT = NAN;
  out.mz_uT = NAN;
  return true;
}

static bool initBmp280() {
  uint8_t id = spiReadReg(BMP_CS_PIN, 0xD0);
  Serial.print("BMP ID: 0x");
  Serial.println(id, HEX);

  if (id != 0x58 && id != 0x60) {
    return false;
  }

  uint8_t cal[24] = {0};
  spiReadRegs(BMP_CS_PIN, 0x88, cal, sizeof(cal));

  bmpCal.dig_T1 = leu16(&cal[0]);
  bmpCal.dig_T2 = les16(&cal[2]);
  bmpCal.dig_T3 = les16(&cal[4]);
  bmpCal.dig_P1 = leu16(&cal[6]);
  bmpCal.dig_P2 = les16(&cal[8]);
  bmpCal.dig_P3 = les16(&cal[10]);
  bmpCal.dig_P4 = les16(&cal[12]);
  bmpCal.dig_P5 = les16(&cal[14]);
  bmpCal.dig_P6 = les16(&cal[16]);
  bmpCal.dig_P7 = les16(&cal[18]);
  bmpCal.dig_P8 = les16(&cal[20]);
  bmpCal.dig_P9 = les16(&cal[22]);

  if (bmpCal.dig_T1 == 0 || bmpCal.dig_P1 == 0) {
    return false;
  }

  spiWriteReg(BMP_CS_PIN, 0xF5, 0x14); // Standby 62.5 ms, filter x16
  spiWriteReg(BMP_CS_PIN, 0xF4, 0x57); // Temp x2, pressure x16, normal mode
  delay(20);
  return true;
}

static float compensateTemp(int32_t adc_T) {
  int32_t var1 = ((((adc_T >> 3) - ((int32_t)bmpCal.dig_T1 << 1))) *
                  ((int32_t)bmpCal.dig_T2)) >> 11;
  int32_t var2 = (((((adc_T >> 4) - ((int32_t)bmpCal.dig_T1)) *
                    ((adc_T >> 4) - ((int32_t)bmpCal.dig_T1))) >> 12) *
                  ((int32_t)bmpCal.dig_T3)) >> 14;
  bmpCal.t_fine = var1 + var2;
  int32_t t = (bmpCal.t_fine * 5 + 128) >> 8;
  return t / 100.0f;
}

static float compensatePressure(int32_t adc_P) {
  int64_t var1 = ((int64_t)bmpCal.t_fine) - 128000;
  int64_t var2 = var1 * var1 * (int64_t)bmpCal.dig_P6;
  var2 = var2 + ((var1 * (int64_t)bmpCal.dig_P5) << 17);
  var2 = var2 + (((int64_t)bmpCal.dig_P4) << 35);
  var1 = ((var1 * var1 * (int64_t)bmpCal.dig_P3) >> 8) +
         ((var1 * (int64_t)bmpCal.dig_P2) << 12);
  var1 = (((((int64_t)1) << 47) + var1)) * ((int64_t)bmpCal.dig_P1) >> 33;
  if (var1 == 0) {
    return NAN;
  }
  int64_t p = 1048576 - adc_P;
  p = (((p << 31) - var2) * 3125) / var1;
  var1 = (((int64_t)bmpCal.dig_P9) * (p >> 13) * (p >> 13)) >> 25;
  var2 = (((int64_t)bmpCal.dig_P8) * p) >> 19;
  p = ((p + var1 + var2) >> 8) + (((int64_t)bmpCal.dig_P7) << 4);
  return p / 256.0f;
}

static bool readBmp280(BaroData &out) {
  uint8_t raw[6] = {0};
  spiReadRegs(BMP_CS_PIN, 0xF7, raw, sizeof(raw));

  int32_t adc_P = ((int32_t)raw[0] << 12) | ((int32_t)raw[1] << 4) | (raw[2] >> 4);
  int32_t adc_T = ((int32_t)raw[3] << 12) | ((int32_t)raw[4] << 4) | (raw[5] >> 4);

  if (adc_P == 0 || adc_P == 0xFFFFF || adc_T == 0 || adc_T == 0xFFFFF) {
    return false;
  }

  out.temp_c = compensateTemp(adc_T);
  out.pressure_pa = compensatePressure(adc_P);
  out.altitude_m = 44330.0f * (1.0f - powf(out.pressure_pa / 101325.0f, 0.1903f));
  return true;
}

static float wrap360(float value) {
  while (value >= 360.0f) value -= 360.0f;
  while (value < 0.0f) value += 360.0f;
  return value;
}

static void updateAttitude(const ImuData &imu, bool imuRead, uint32_t nowMs,
                           float &roll, float &pitch, float &heading) {
  roll = NAN;
  pitch = NAN;

  if (imuRead) {
    roll = atan2f(imu.ay_g, imu.az_g) * 57.2957795f;
    pitch = atan2f(-imu.ax_g, sqrtf(imu.ay_g * imu.ay_g + imu.az_g * imu.az_g)) * 57.2957795f;

    if (lastYawMs != 0) {
      float dt = (nowMs - lastYawMs) * 0.001f;
      if (dt > 0.0f && dt < 1.0f) {
        yawDeg = wrap360(yawDeg + imu.gz_dps * dt);
      }
    }
    lastYawMs = nowMs;
  }

  heading = wrap360(yawDeg);
}

static float selectControlAngle(float rollDeg, float pitchDeg) {
#if CONTROL_AXIS_PITCH
  return CONTROL_SIGN * pitchDeg;
#else
  return CONTROL_SIGN * rollDeg;
#endif
}

static float selectControlRate(const ImuData &imu) {
#if CONTROL_AXIS_PITCH
  return CONTROL_SIGN * imu.gy_dps;
#else
  return CONTROL_SIGN * imu.gx_dps;
#endif
}

static float pwmToOmega(float pwmUs) {
  float pwmEff = pwmUs < 1040.0f ? (float)minPwm : pwmUs;
  float throttle = (pwmEff - (float)minPwm) / (float)(maxPwm - minPwm);
  throttle = clampFloat(throttle, 0.0f, 1.0f);
  return plantMaxOmega * throttle;
}

static bool updateKalmanObserver(float measuredAngleDeg, float measuredRateDps,
                                 float pwmLeftUs, float pwmRightUs) {
  if (!isfinite(measuredAngleDeg) || !isfinite(measuredRateDps)) {
    return false;
  }

  float measuredTheta = measuredAngleDeg * degToRad;
  float measuredRate = measuredRateDps * degToRad;

  if (!observer.initialized) {
    observer.theta_rad = measuredTheta;
    observer.theta_dot_rad_s = measuredRate;
    observer.omega_left_rad_s = pwmToOmega(pwmLeftUs);
    observer.omega_right_rad_s = pwmToOmega(pwmRightUs);
    observer.p00 = powf(kalmanRAngle * degToRad, 2.0f);
    observer.p01 = 0.0f;
    observer.p10 = 0.0f;
    observer.p11 = powf(kalmanRRate * degToRad, 2.0f);
    observer.initialized = true;
    return true;
  }

  float omegaCmdLeft = pwmToOmega(pwmLeftUs);
  float omegaCmdRight = pwmToOmega(pwmRightUs);
  observer.omega_left_rad_s += Ts * (omegaCmdLeft - observer.omega_left_rad_s) /
                               fmaxf(plantTauMotor, Ts);
  observer.omega_right_rad_s += Ts * (omegaCmdRight - observer.omega_right_rad_s) /
                                fmaxf(plantTauMotor, Ts);
  observer.omega_left_rad_s = fmaxf(0.0f, observer.omega_left_rad_s);
  observer.omega_right_rad_s = fmaxf(0.0f, observer.omega_right_rad_s);

  float tauLeft = plantArmLeftM * plantKf * observer.omega_left_rad_s *
                  observer.omega_left_rad_s;
  float tauRight = plantArmRightM * plantKf * observer.omega_right_rad_s *
                   observer.omega_right_rad_s;
  float thetaDDot = (tauRight - tauLeft -
                     plantDamping * observer.theta_dot_rad_s -
                     plantGravity * sinf(observer.theta_rad)) /
                    fmaxf(plantInertia, 0.0001f);

  observer.theta_rad += Ts * observer.theta_dot_rad_s + 0.5f * Ts * Ts * thetaDDot;
  observer.theta_dot_rad_s += Ts * thetaDDot;

  float qAngle = powf(kalmanQAngle * degToRad, 2.0f);
  float qRate = powf(kalmanQRate * degToRad, 2.0f);
  float p00 = observer.p00 + Ts * (observer.p10 + observer.p01) +
              Ts * Ts * observer.p11 + qAngle;
  float p01 = observer.p01 + Ts * observer.p11;
  float p10 = observer.p10 + Ts * observer.p11;
  float p11 = observer.p11 + qRate;

  float rAngle = powf(kalmanRAngle * degToRad, 2.0f);
  float yAngle = measuredTheta - observer.theta_rad;
  float sAngle = p00 + rAngle;
  if (sAngle > 1.0e-9f) {
    float k0 = p00 / sAngle;
    float k1 = p10 / sAngle;
    observer.theta_rad += k0 * yAngle;
    observer.theta_dot_rad_s += k1 * yAngle;
    float oldP00 = p00;
    float oldP01 = p01;
    p00 -= k0 * oldP00;
    p01 -= k0 * oldP01;
    p10 -= k1 * oldP00;
    p11 -= k1 * oldP01;
  }

  float rRate = powf(kalmanRRate * degToRad, 2.0f);
  float yRate = measuredRate - observer.theta_dot_rad_s;
  float sRate = p11 + rRate;
  if (sRate > 1.0e-9f) {
    float k0 = p01 / sRate;
    float k1 = p11 / sRate;
    observer.theta_rad += k0 * yRate;
    observer.theta_dot_rad_s += k1 * yRate;
    float oldP10 = p10;
    float oldP11 = p11;
    p00 -= k0 * oldP10;
    p01 -= k0 * oldP11;
    p10 -= k1 * oldP10;
    p11 -= k1 * oldP11;
  }

  observer.p00 = fmaxf(p00, 1.0e-10f);
  observer.p01 = p01;
  observer.p10 = p10;
  observer.p11 = fmaxf(p11, 1.0e-10f);

  return isfinite(observer.theta_rad) && isfinite(observer.theta_dot_rad_s);
}

static void setupMotorPwm() {
  leftMotor.attach(LEFT_PWM_PIN, minPwm, maxPwm);
  rightMotor.attach(RIGHT_PWM_PIN, minPwm, maxPwm);
  leftMotor.writeMicroseconds(minPwm);
  rightMotor.writeMicroseconds(minPwm);
}

static void writeMotorPwm(int leftUs, int rightUs) {
  leftUs = clampInt(leftUs, minPwm, maxPwm);
  rightUs = clampInt(rightUs, minPwm, maxPwm);
  leftMotor.writeMicroseconds(leftUs);
  rightMotor.writeMicroseconds(rightUs);
}

static void stopMotorOverride() {
  motorOverrideActive = false;
  motorOverrideUntilMs = 0;
  motorOverrideLeftUs = minPwm;
  motorOverrideRightUs = minPwm;
  control.pwm_left_us = (float)minPwm;
  control.pwm_right_us = (float)minPwm;
  writeMotorPwm(minPwm, minPwm);
}

static void startMotorOverride(int leftUs, int rightUs, uint32_t durationMs) {
  control.armed = false;
  control.safety_latched = false;
  control.integral_error = 0.0f;
  control.u_diff_us = 0.0f;
  motorOverrideLeftUs = clampInt(leftUs, minPwm, motorTestMaxPwm);
  motorOverrideRightUs = clampInt(rightUs, minPwm, motorTestMaxPwm);
  motorOverrideUntilMs = millis() + constrain(durationMs, 250UL, 10000UL);
  motorOverrideActive = true;
  control.pwm_left_us = (float)motorOverrideLeftUs;
  control.pwm_right_us = (float)motorOverrideRightUs;
  writeMotorPwm(motorOverrideLeftUs, motorOverrideRightUs);
}

static bool serviceMotorOverride(uint32_t nowMs) {
  if (!motorOverrideActive) {
    return false;
  }
  if ((int32_t)(nowMs - motorOverrideUntilMs) >= 0) {
    stopMotorOverride();
    return false;
  }
  control.pwm_left_us = (float)motorOverrideLeftUs;
  control.pwm_right_us = (float)motorOverrideRightUs;
  writeMotorPwm(motorOverrideLeftUs, motorOverrideRightUs);
  return true;
}

static void disarmController(bool latchSafety) {
  stopMotorOverride();
  control.armed = false;
  if (latchSafety) {
    control.safety_latched = true;
  }
  control.integral_error = 0.0f;
  control.filtered_rate_dps = 0.0f;
  control.error_deg = 0.0f;
  control.u_diff_us = 0.0f;
  control.pwm_left_us = (float)minPwm;
  control.pwm_right_us = (float)minPwm;
  writeMotorPwm(minPwm, minPwm);
}

static bool canArmController() {
  if (!mpuOk || !isfinite(control.angle_deg)) {
    return false;
  }
  return true;
}

static bool armController() {
  if (!canArmController()) {
    control.safety_latched = true;
    disarmController(true);
    return false;
  }

  control.safety_latched = false;
  control.armed = true;
  control.integral_error = 0.0f;
  control.filtered_rate_dps = isfinite(control.rate_dps) ? control.rate_dps : 0.0f;
  control.error_deg = 0.0f;
  control.u_diff_us = 0.0f;
  control.pwm_left_us = (float)minPwm;
  control.pwm_right_us = (float)minPwm;
  writeMotorPwm(minPwm, minPwm);
  return true;
}

static int roundedPwm(float value) {
  float rounded = roundf(value / (float)pwmResolution) * (float)pwmResolution;
  return clampInt((int)rounded, minPwm, maxPwm);
}

static void runController(float angleDeg, float rateDps, bool imuRead) {
  const uint32_t nowUs = micros();
  const uint32_t periodUs = 1000000UL / CONTROL_HZ;

  if (lastControlUs == 0) {
    lastControlUs = nowUs;
    return;
  }

  if ((uint32_t)(nowUs - lastControlUs) < periodUs) {
    return;
  }

  if ((uint32_t)(nowUs - lastControlUs) > periodUs * 5UL) {
    lastControlUs = nowUs;
  } else {
    lastControlUs += periodUs;
  }

  bool observerOk = imuRead && updateKalmanObserver(
    angleDeg,
    rateDps,
    control.pwm_left_us,
    control.pwm_right_us
  );

  float estimatedAngleDeg = observerOk ? observer.theta_rad * radToDeg : angleDeg;
  float estimatedRateDps = observerOk ? observer.theta_dot_rad_s * radToDeg : rateDps;

  control.angle_deg = estimatedAngleDeg;
  control.rate_dps = estimatedRateDps;

  if (!control.armed) {
    writeMotorPwm(minPwm, minPwm);
    return;
  }

  if (!observerOk || !isfinite(estimatedAngleDeg) || !isfinite(estimatedRateDps)) {
    disarmController(true);
    return;
  }

  float alpha = Ts / (derivativeTau + Ts);
  control.filtered_rate_dps += alpha * (estimatedRateDps - control.filtered_rate_dps);

  float error = control.reference_deg - estimatedAngleDeg;
  float uRaw = gains.Kp * error + gains.Ki * control.integral_error -
               gains.Kd * control.filtered_rate_dps;
  float uSat = clampFloat(uRaw, -(float)maxDiffPwm, (float)maxDiffPwm);

  float trackingGain = 1.0f / fmaxf(antiWindupTau, Ts);
  control.integral_error += Ts * (error + trackingGain * (uSat - uRaw));

  if (gains.Ki > 0.0001f) {
    float intMax = integratorLimit / gains.Ki;
    control.integral_error = clampFloat(control.integral_error, -intMax, intMax);
  }

  float u = gains.Kp * error + gains.Ki * control.integral_error -
            gains.Kd * control.filtered_rate_dps;
  u = clampFloat(u, -(float)maxDiffPwm, (float)maxDiffPwm);
  u *= MOTOR_MIX_SIGN;

  float pwmLeftTarget = clampFloat((float)hoverPwm - u, (float)armedMinPwm, (float)maxPwm);
  float pwmRightTarget = clampFloat((float)hoverPwm + u, (float)armedMinPwm, (float)maxPwm);
  float maxStep = pwmSlewRate * Ts;

  control.pwm_left_us += clampFloat(pwmLeftTarget - control.pwm_left_us, -maxStep, maxStep);
  control.pwm_right_us += clampFloat(pwmRightTarget - control.pwm_right_us, -maxStep, maxStep);

  int pwmLeft = roundedPwm(control.pwm_left_us);
  int pwmRight = roundedPwm(control.pwm_right_us);

  control.error_deg = error;
  control.u_diff_us = u;
  control.pwm_left_us = (float)pwmLeft;
  control.pwm_right_us = (float)pwmRight;
  writeMotorPwm(pwmLeft, pwmRight);
}

static uint8_t telemetryChecksum(const TelemetryPacketV2 &pkt) {
  const uint8_t *payload = &pkt.version;
  const size_t payloadLen = sizeof(TelemetryPacketV2) - 3; // sync0, sync1, checksum
  uint8_t checksum = 0;
  for (size_t i = 0; i < payloadLen; ++i) {
    checksum ^= payload[i];
  }
  return checksum;
}

static void writePacket(Stream &stream, const TelemetryPacketV2 &pkt) {
  stream.write(reinterpret_cast<const uint8_t *>(&pkt), sizeof(pkt));
}

static TelemetryPacketV2 makePacket(const ImuData &imu, const BaroData &baro,
                                    bool imuRead, bool baroRead,
                                    float roll, float pitch, float heading) {
  const uint32_t now = millis();

  float altitudeFt = NAN;
  float verticalSpeedFpm = NAN;
  if (baroRead) {
    altitudeFt = baro.altitude_m * 3.28084f;
    if (!isnan(lastAltitudeFt) && lastAltitudeSampleMs != 0) {
      float dt = (now - lastAltitudeSampleMs) * 0.001f;
      if (dt > 0.0f && dt < 1.0f) {
        float rawVs = (altitudeFt - lastAltitudeFt) / dt * 60.0f;
        filteredVerticalSpeedFpm = 0.85f * filteredVerticalSpeedFpm + 0.15f * rawVs;
      }
    }
    verticalSpeedFpm = filteredVerticalSpeedFpm;
    lastAltitudeFt = altitudeFt;
    lastAltitudeSampleMs = now;
  }

  TelemetryPacketV2 pkt = {};
  pkt.sync0 = 0xAA;
  pkt.sync1 = 0x55;
  pkt.version = 2;
  pkt.flags = (imuRead ? 0x01 : 0x00) |
              (baroRead ? 0x02 : 0x00) |
              (control.armed ? 0x04 : 0x00) |
              (control.safety_latched ? 0x08 : 0x00);
  pkt.time_ms = now;
  pkt.roll_deg = roll;
  pkt.pitch_deg = pitch;
  pkt.heading_deg = heading;
  pkt.altitude_ft = altitudeFt;
  pkt.vertical_speed_fpm = verticalSpeedFpm;
  pkt.control_ref_deg = control.reference_deg;
  pkt.control_angle_deg = control.angle_deg;
  pkt.control_rate_dps = control.rate_dps;
  pkt.control_error_deg = control.error_deg;
  pkt.control_u_diff_us = control.u_diff_us;
  pkt.pwm_left_us = control.pwm_left_us;
  pkt.pwm_right_us = control.pwm_right_us;
  pkt.ax_g = imuRead ? imu.ax_g : NAN;
  pkt.ay_g = imuRead ? imu.ay_g : NAN;
  pkt.az_g = imuRead ? imu.az_g : NAN;
  pkt.gx_dps = imuRead ? imu.gx_dps : NAN;
  pkt.gy_dps = imuRead ? imu.gy_dps : NAN;
  pkt.gz_dps = imuRead ? imu.gz_dps : NAN;
  pkt.pressure_pa = baroRead ? baro.pressure_pa : NAN;
  pkt.imu_temp_c = imuRead ? imu.temp_c : NAN;
  pkt.bmp_temp_c = baroRead ? baro.temp_c : NAN;
  pkt.checksum = telemetryChecksum(pkt);
  return pkt;
}

static void sendTelemetryPacket(const TelemetryPacketV2 &pkt) {
  writePacket(Serial, pkt);
}

static char *trimWhitespace(char *text) {
  while (*text && isspace((unsigned char)*text)) {
    ++text;
  }

  char *end = text + strlen(text);
  while (end > text && isspace((unsigned char)*(end - 1))) {
    --end;
  }
  *end = '\0';
  return text;
}

static char *skipSeparators(char *text) {
  while (*text == ' ' || *text == '\t' || *text == ',' || *text == ';') {
    ++text;
  }
  return text;
}

static void uppercaseToken(char *text) {
  while (*text) {
    *text = (char)toupper((unsigned char)*text);
    ++text;
  }
}

static bool parseFloatList(char *args, float *values, size_t count) {
  char *cursor = args;
  for (size_t i = 0; i < count; ++i) {
    cursor = skipSeparators(cursor);
    char *end = nullptr;
    values[i] = strtof(cursor, &end);
    if (end == cursor) {
      return false;
    }
    cursor = end;
  }
  return true;
}

static bool parseIntArg(char *args, int &value) {
  char *cursor = skipSeparators(args);
  char *end = nullptr;
  long parsed = strtol(cursor, &end, 10);
  if (end == cursor) {
    return false;
  }
  value = (int)parsed;
  return true;
}

static void printStatus(Stream &reply) {
  reply.print("STATUS,ARM=");
  reply.print(control.armed ? 1 : 0);
  reply.print(",SAFE=");
  reply.print(control.safety_latched ? 0 : 1);
  reply.print(",REF=");
  reply.print(control.reference_deg, 3);
  reply.print(",ANGLE=");
  reply.print(control.angle_deg, 3);
  reply.print(",KP=");
  reply.print(gains.Kp, 6);
  reply.print(",KI=");
  reply.print(gains.Ki, 6);
  reply.print(",KD=");
  reply.print(gains.Kd, 6);
  reply.print(",HOVER=");
  reply.print(hoverPwm);
  reply.print(",IDLE=");
  reply.print(armedMinPwm);
  reply.print(",KAL=");
  reply.print(kalmanQAngle, 3);
  reply.print("/");
  reply.print(kalmanQRate, 3);
  reply.print("/");
  reply.print(kalmanRAngle, 3);
  reply.print("/");
  reply.print(kalmanRRate, 3);
  reply.print(",TEST=");
  reply.println(motorOverrideActive ? 1 : 0);
}

static void processCommand(char *rawLine, Stream &reply) {
  char *line = trimWhitespace(rawLine);
  if (*line == '\0') {
    return;
  }

  char *args = line;
  while (*args && *args != ' ' && *args != '\t' && *args != ',' && *args != ';') {
    ++args;
  }
  if (*args) {
    *args = '\0';
    ++args;
  }
  args = skipSeparators(args);
  uppercaseToken(line);

  if (strcmp(line, "ARM") == 0) {
    int requested = 0;
    if (!parseIntArg(args, requested)) {
      reply.println("ERR,ARM,ARG");
      return;
    }
    if (requested) {
      if (armController()) {
        reply.println("OK,ARM,1");
      } else {
        reply.println("ERR,ARM,UNSAFE");
      }
    } else {
      control.safety_latched = false;
      disarmController(false);
      reply.println("OK,ARM,0");
    }
    return;
  }

  if (strcmp(line, "DISARM") == 0) {
    control.safety_latched = false;
    disarmController(false);
    reply.println("OK,ARM,0");
    return;
  }

  if (strcmp(line, "REF") == 0) {
    float value = 0.0f;
    if (!parseFloatList(args, &value, 1)) {
      reply.println("ERR,REF,ARG");
      return;
    }
    control.reference_deg = clampFloat(value, -maxSafeAngleDeg, maxSafeAngleDeg);
    reply.print("OK,REF,");
    reply.println(control.reference_deg, 3);
    return;
  }

  if (strcmp(line, "PID") == 0) {
    float values[3] = {0.0f, 0.0f, 0.0f};
    if (!parseFloatList(args, values, 3)) {
      reply.println("ERR,PID,ARG");
      return;
    }
    gains.Kp = clampFloat(values[0], 0.0f, 10.0f);
    gains.Ki = clampFloat(values[1], 0.0f, 10.0f);
    gains.Kd = clampFloat(values[2], 0.0f, 5.0f);
    control.integral_error = 0.0f;
    reply.print("OK,PID,");
    reply.print(gains.Kp, 6);
    reply.print(",");
    reply.print(gains.Ki, 6);
    reply.print(",");
    reply.println(gains.Kd, 6);
    return;
  }

  if (strcmp(line, "KAL") == 0) {
    float values[4] = {0.0f, 0.0f, 0.0f, 0.0f};
    if (!parseFloatList(args, values, 4)) {
      reply.println("ERR,KAL,ARG");
      return;
    }
    kalmanQAngle = clampFloat(values[0], 0.001f, 5.0f);
    kalmanQRate = clampFloat(values[1], 0.01f, 80.0f);
    kalmanRAngle = clampFloat(values[2], 0.05f, 30.0f);
    kalmanRRate = clampFloat(values[3], 0.5f, 200.0f);
    observer.initialized = false;
    reply.print("OK,KAL,");
    reply.print(kalmanQAngle, 3);
    reply.print(",");
    reply.print(kalmanQRate, 3);
    reply.print(",");
    reply.print(kalmanRAngle, 3);
    reply.print(",");
    reply.println(kalmanRRate, 3);
    return;
  }

  if (strcmp(line, "HOVER") == 0) {
    int value = hoverPwm;
    if (!parseIntArg(args, value)) {
      reply.println("ERR,HOVER,ARG");
      return;
    }
    hoverPwm = clampInt(value, minPwm, maxPwm);
    reply.print("OK,HOVER,");
    reply.println(hoverPwm);
    return;
  }

  if (strcmp(line, "IDLE") == 0) {
    int value = armedMinPwm;
    if (!parseIntArg(args, value)) {
      reply.println("ERR,IDLE,ARG");
      return;
    }
    armedMinPwm = clampInt(value, minPwm, hoverPwm);
    reply.print("OK,IDLE,");
    reply.println(armedMinPwm);
    return;
  }

  if (strcmp(line, "MOTOR") == 0) {
    float values[3] = {0.0f, 0.0f, 0.0f};
    if (!parseFloatList(args, values, 3)) {
      reply.println("ERR,MOTOR,ARG");
      return;
    }
    int leftUs = clampInt((int)roundf(values[0]), minPwm, motorTestMaxPwm);
    int rightUs = clampInt((int)roundf(values[1]), minPwm, motorTestMaxPwm);
    uint32_t durationMs = (uint32_t)clampFloat(values[2], 250.0f, 10000.0f);
    startMotorOverride(leftUs, rightUs, durationMs);
    reply.print("OK,MOTOR,");
    reply.print(leftUs);
    reply.print(",");
    reply.print(rightUs);
    reply.print(",");
    reply.println(durationMs);
    return;
  }

  if (strcmp(line, "STATUS") == 0) {
    printStatus(reply);
    return;
  }

  reply.print("ERR,UNKNOWN,");
  reply.println(line);
}

static void pollCommandStream(Stream &stream, char *buffer, size_t &length) {
  while (stream.available() > 0) {
    int value = stream.read();
    if (value < 0) {
      return;
    }

    char ch = (char)value;
    if (ch == '\r') {
      continue;
    }
    if (ch == '\n') {
      buffer[length] = '\0';
      processCommand(buffer, stream);
      length = 0;
      continue;
    }

    if ((unsigned char)ch < 32 || (unsigned char)ch > 126) {
      continue;
    }

    if (length < 95) {
      buffer[length++] = ch;
    } else {
      length = 0;
    }
  }
}

void setup() {
  setupMotorPwm();
  disarmController(false);

  delay(1000);
  Serial.begin(SERIAL_BAUD);
  delay(500);

  delay(1200);

  pinMode(MPU_CS_PIN, OUTPUT);
  pinMode(BMP_CS_PIN, OUTPUT);
  csHigh();

  SPI.setSCLK(SPI_SCK_PIN);
  SPI.setMISO(SPI_MISO_PIN);
  SPI.setMOSI(SPI_MOSI_PIN);
  SPI.begin();

  Serial.println();
  Serial.println("STM32F401 GY-91 SPI 1DOF PID controller");
  Serial.println("SPI pins: SCK=PA5 MISO=PA6 MOSI=PA7 MPU_NCS=PB0 BMP_CSB=PB1");
  Serial.println("PWM pins: LEFT=A2/PA2 RIGHT=A3/PA3");
  Serial.println("Commands: ARM,1 ARM,0 REF,<deg> PID,<kp>,<ki>,<kd> KAL,<qA>,<qR>,<rA>,<rR> HOVER,<us> IDLE,<us> MOTOR,<l>,<r>,<ms> STATUS");

  mpuOk = initMpu();
  bmpOk = initBmp280();

  Serial.print("MPU: ");
  Serial.println(mpuOk ? "OK" : "not found");
  Serial.print("BMP280/BME280: ");
  Serial.println(bmpOk ? "OK" : "not found");
  Serial.print("Tuned PID: ");
  Serial.print(gains.Kp, 6);
  Serial.print(", ");
  Serial.print(gains.Ki, 6);
  Serial.print(", ");
  Serial.println(gains.Kd, 6);

  lastControlUs = micros();
}

void loop() {
  pollCommandStream(Serial, usbCommandBuffer, usbCommandLen);

  ImuData imu = {NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN};
  BaroData baro = {NAN, NAN, NAN};

  bool imuRead = mpuOk && readMpu(imu);
  bool baroRead = bmpOk && readBmp280(baro);

  const uint32_t nowMs = millis();
  float roll = NAN;
  float pitch = NAN;
  float heading = NAN;
  updateAttitude(imu, imuRead, nowMs, roll, pitch, heading);

  float controlAngle = imuRead ? selectControlAngle(roll, pitch) : NAN;
  float controlRate = imuRead ? selectControlRate(imu) : NAN;
  if (!serviceMotorOverride(nowMs)) {
    runController(controlAngle, controlRate, imuRead);
  }

  const uint32_t periodMs = 1000 / TELEMETRY_HZ;
  if (nowMs - lastTelemetryMs >= periodMs) {
    lastTelemetryMs = nowMs;
    TelemetryPacketV2 pkt = makePacket(imu, baro, imuRead, baroRead, roll, pitch, heading);
    sendTelemetryPacket(pkt);
  }
}
