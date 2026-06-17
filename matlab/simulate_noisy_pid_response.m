function sim = simulate_noisy_pid_response(gains, p, showPlot)
%SIMULATE_NOISY_PID_RESPONSE Discrete closed-loop sim with sensor noise.
%
% This is the best match to the embedded controller path: the controller
% receives noisy sampled measurements, then the plant is advanced one sample.

if nargin < 2
    p = init_1dof_params();
end
if nargin < 3
    showPlot = true;
end
if nargin < 1 || isempty(gains)
    data = load(fullfile('output', 'tuned_pid_gains.mat'), 'gains');
    gains = data.gains;
end

rng(p.noiseSeed);
n = floor(p.simTime / p.Ts) + 1;
t = (0:n-1)' * p.Ts;

theta = zeros(n, 1);
thetaDot = zeros(n, 1);
omegaLeft = zeros(n, 1);
omegaRight = zeros(n, 1);
thetaMeas = zeros(n, 1);
uDiff = zeros(n, 1);
pwmLeft = zeros(n, 1);
pwmRight = zeros(n, 1);
integral = zeros(n, 1);
isSaturated = false(n, 1);
refDeg = nan(n, 1);

theta(1) = deg2rad(p.theta0Deg);
omegaLeft(1) = pwm_to_omega(p.hoverPwm, p);
omegaRight(1) = pwm_to_omega(p.hoverPwm, p);

refSequenceDeg = p.refDeg;
if isfield(p, 'refSequenceDeg') && ~isempty(p.refSequenceDeg)
    refSequenceDeg = p.refSequenceDeg(:)';
end
refIndex = 1;
steadySamplesNeeded = max(1, round(p.steadyMinTime / p.Ts));
holdSamplesNeeded = max(1, round(p.refHoldAfterSteady / p.Ts));
steadyCount = 0;
holdCount = 0;
steadyLatched = false;
ctrlState = struct('integral', 0, 'dFilt', 0, ...
    'pwmLeft', p.hoverPwm, 'pwmRight', p.hoverPwm);

for k = 1:n-1
    refDeg(k) = refSequenceDeg(refIndex);

    noiseAngle = deg2rad(p.sensorNoiseStdDeg) * randn();
    noiseRate = deg2rad(p.sensorRateNoiseStdDegS) * randn();
    thetaMeas(k) = theta(k) + noiseAngle;
    thetaRateMeas = thetaDot(k) + noiseRate;

    [cmd, ctrlState] = pid_antiwindup_step(rad2deg(thetaMeas(k)), ...
        rad2deg(thetaRateMeas), refDeg(k), gains, p, ctrlState);
    uDiff(k) = cmd.uDiff;
    pwmLeft(k) = cmd.pwmLeft;
    pwmRight(k) = cmd.pwmRight;
    integral(k) = cmd.integral;
    isSaturated(k) = cmd.isSaturated;

    omegaCmdLeft = pwm_to_omega(pwmLeft(k), p);
    omegaCmdRight = pwm_to_omega(pwmRight(k), p);

    tauLeft = p.L1 * p.kf * omegaLeft(k)^2;
    tauRight = p.L2 * p.kf * omegaRight(k)^2;
    tauDist = 0;
    if t(k) >= p.disturbanceTime
        tauDist = p.disturbanceTorque;
    end

    thetaDDot = (tauRight - tauLeft + tauDist ...
        - p.c * thetaDot(k) - p.mgl * sin(theta(k))) / p.J;

    theta(k+1) = theta(k) + p.Ts * thetaDot(k);
    thetaDot(k+1) = thetaDot(k) + p.Ts * thetaDDot;
    omegaLeft(k+1) = omegaLeft(k) + p.Ts * (omegaCmdLeft - omegaLeft(k)) / p.tauMotor;
    omegaRight(k+1) = omegaRight(k) + p.Ts * (omegaCmdRight - omegaRight(k)) / p.tauMotor;

    if refIndex < numel(refSequenceDeg)
        steadyError = abs(rad2deg(theta(k+1)) - refSequenceDeg(refIndex));
        steadyRate = abs(rad2deg(thetaDot(k+1)));
        if ~steadyLatched
            if steadyError <= p.steadyErrorDeg && steadyRate <= p.steadyRateDegS
                steadyCount = steadyCount + 1;
            else
                steadyCount = 0;
            end
            steadyLatched = steadyCount >= steadySamplesNeeded;
        else
            holdCount = holdCount + 1;
            if holdCount >= holdSamplesNeeded
                refIndex = refIndex + 1;
                steadyCount = 0;
                holdCount = 0;
                steadyLatched = false;
            end
        end
    end

    if abs(rad2deg(theta(k+1))) > p.maxSafeAngleDeg
        theta(k+2:end) = theta(k+1);
        thetaDot(k+1:end) = 0;
        omegaLeft(k+1:end) = omegaLeft(k+1);
        omegaRight(k+1:end) = omegaRight(k+1);
        pwmLeft(k+1:end) = pwmLeft(k);
        pwmRight(k+1:end) = pwmRight(k);
        uDiff(k+1:end) = uDiff(k);
        integral(k+1:end) = integral(k);
        isSaturated(k+1:end) = true;
        refDeg(k+1:end) = refSequenceDeg(refIndex);
        break;
    end
end

if isnan(refDeg(end))
    refDeg(end) = refDeg(max(1, end-1));
end
thetaMeas(end) = theta(end) + deg2rad(p.sensorNoiseStdDeg) * randn();
uDiff(end) = uDiff(end-1);
pwmLeft(end) = pwmLeft(end-1);
pwmRight(end) = pwmRight(end-1);

sim = struct();
sim.t = t;
sim.thetaDeg = rad2deg(theta);
sim.thetaMeasDeg = rad2deg(thetaMeas);
sim.thetaDotDegS = rad2deg(thetaDot);
sim.uDiff = uDiff;
sim.pwmLeft = pwmLeft;
sim.pwmRight = pwmRight;
sim.integral = integral;
sim.isSaturated = isSaturated;
sim.refDeg = refDeg;

if ~showPlot
    return;
end

figure('Name', '1-DOF Copter Noisy PID Response');
tiledlayout(3, 1);

nexttile;
plot(t, sim.thetaDeg, 'LineWidth', 1.5);
hold on;
plot(t, sim.thetaMeasDeg, '.', 'MarkerSize', 4);
stairs(t, sim.refDeg, '--', 'LineWidth', 1.3);
grid on;
ylabel('theta (deg)');
legend('true', 'measured', 'reference', 'Location', 'best');

nexttile;
plot(t, uDiff, 'LineWidth', 1.5);
hold on;
yline(p.maxDiffPwm, '--');
yline(-p.maxDiffPwm, '--');
grid on;
ylabel('diff PWM (us)');

nexttile;
plot(t, pwmLeft, 'LineWidth', 1.2);
hold on;
plot(t, pwmRight, 'LineWidth', 1.2);
grid on;
ylabel('PWM (us)');
xlabel('time (s)');
legend('left', 'right', 'Location', 'best');
end
