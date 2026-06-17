function p = init_1dof_params()
%INIT_1DOF_PARAMS Default parameters for a 1-DOF copter test rig.
%
% Replace these values with measured values from your physical build before
% using the tuned gains on hardware.

p = struct();

% Geometry and rigid body parameters
p.L1 = 0.25;                 % m, pivot to left rotor
p.L2 = 0.25;                 % m, pivot to right rotor
p.J = 0.018;                 % kg*m^2, beam + mounted hardware inertia
p.c = 0.012;                 % N*m*s/rad, pivot viscous friction
p.mgl = 0.040;               % N*m, gravity moment coefficient

% Motor and propeller model
p.motorName = 'XA2212_820KV';
p.propName = '1045';         % 10x4.5 propeller, from "FT 1045" marking
p.motorKv = 820;             % rpm/V
p.batteryVoltage = 11.1;     % V, assumed 3S LiPo nominal voltage
p.loadedRpmFactor = 0.82;    % no-load to loaded prop speed estimate
p.maxOmega = p.motorKv * p.batteryVoltage * 2*pi/60 * p.loadedRpmFactor;
p.kf = 1.85e-5;              % N/(rad/s)^2, rough 1045 prop estimate
p.tauMotor = 0.055;          % s, motor/prop speed lag after ideal ESC command
p.escModel = 'ideal_linear_pwm_to_throttle';

% PWM and actuator limits
p.minPwm = 1000;             % us
p.maxPwm = 2000;             % us
p.hoverPwm = 1180;           % us, adjust from experiment
p.maxDiffPwm = 350;          % us, differential command clamp
p.pwmSlewRate = 900;         % us/s, ESC command rate limit
p.pwmResolution = 1;         % us, command quantization
p.motorDeadbandPwm = 1040;   % us, below this the motor is treated as stopped
p.maxSafeAngleDeg = 35;      % deg, simulation safety stop

% Simulation and control settings
p.Ts = 0.01;                 % s, embedded controller sample time
p.simTime = 20.0;            % s
p.refDeg = 10;               % deg, target angle for tuning
p.refSequenceDeg = [10 0 -20]; % deg, automatic video/simulation sequence
p.refHoldAfterSteady = 3.0;  % s, wait this long after steady before next ref
p.steadyErrorDeg = 1.0;      % deg, steady-state angle error threshold
p.steadyRateDegS = 2.0;      % deg/s, steady-state rate threshold
p.steadyMinTime = 0.5;       % s, must remain steady before hold timer starts
p.theta0Deg = 0;             % deg
p.sensorNoiseStdDeg = 0.35;  % deg, Gaussian angle measurement noise
p.sensorRateNoiseStdDegS = 3.0; % deg/s, Gaussian rate measurement noise
p.noiseSeed = 11;
p.disturbanceTime = 3.0;     % s
p.disturbanceTorque = 0.012; % N*m

% PID implementation settings. Gains use degree-based units:
% Kp us/deg, Ki us/(deg*s), Kd us/(deg/s).
p.integratorLimit = 120;     % pwm-equivalent integrator contribution clamp
p.derivativeTau = 0.035;     % s, derivative low-pass time constant
p.antiWindupTau = 0.18;      % s, back-calculation anti-windup time constant

% PSO settings
p.psoParticles = 24;
p.psoIterations = 45;
p.psoSeed = 7;
p.KpBounds = [0 2.2];
p.KiBounds = [0 1.4];
p.KdBounds = [0 0.45];

% Cost weights
p.wTrack = 1.0;
p.wOvershoot = 15.0;
p.wSettling = 0.35;
p.wEffort = 0.00025;
p.wSaturation = 0.8;
p.wFinalError = 30.0;
end
