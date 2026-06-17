function [cmd, state] = pid_antiwindup_step(thetaMeasDeg, thetaRateMeasDegS, refDeg, gains, p, state)
%PID_ANTIWINDUP_STEP Discrete PID with derivative filtering and anti-windup.
%
% Units are degrees, degrees/s, PWM microseconds, and seconds. This keeps
% hardware gains intuitive: Kp is PWM microseconds per degree of error.

if ~isfield(state, 'integral')
    state.integral = 0;
end
if ~isfield(state, 'dFilt')
    state.dFilt = thetaRateMeasDegS;
end
if ~isfield(state, 'pwmLeft')
    state.pwmLeft = p.hoverPwm;
end
if ~isfield(state, 'pwmRight')
    state.pwmRight = p.hoverPwm;
end

err = refDeg - thetaMeasDeg;
alpha = p.Ts / max(p.derivativeTau + p.Ts, eps);
state.dFilt = state.dFilt + alpha * (thetaRateMeasDegS - state.dFilt);

uUnsat = gains.Kp * err + gains.Ki * state.integral - gains.Kd * state.dFilt;
uSat = min(max(uUnsat, -p.maxDiffPwm), p.maxDiffPwm);

trackGain = 1 / max(p.antiWindupTau, p.Ts);
state.integral = state.integral + p.Ts * (err + trackGain * (uSat - uUnsat));

if gains.Ki > eps
    intLimit = p.integratorLimit / gains.Ki;
    state.integral = min(max(state.integral, -intLimit), intLimit);
end

uAfterAw = gains.Kp * err + gains.Ki * state.integral - gains.Kd * state.dFilt;
uDiff = min(max(uAfterAw, -p.maxDiffPwm), p.maxDiffPwm);

pwmLeftTarget = min(max(p.hoverPwm - uDiff, p.minPwm), p.maxPwm);
pwmRightTarget = min(max(p.hoverPwm + uDiff, p.minPwm), p.maxPwm);

maxStep = p.pwmSlewRate * p.Ts;
pwmLeft = state.pwmLeft + min(max(pwmLeftTarget - state.pwmLeft, -maxStep), maxStep);
pwmRight = state.pwmRight + min(max(pwmRightTarget - state.pwmRight, -maxStep), maxStep);

pwmLeft = round(pwmLeft / p.pwmResolution) * p.pwmResolution;
pwmRight = round(pwmRight / p.pwmResolution) * p.pwmResolution;
pwmLeft = min(max(pwmLeft, p.minPwm), p.maxPwm);
pwmRight = min(max(pwmRight, p.minPwm), p.maxPwm);

state.pwmLeft = pwmLeft;
state.pwmRight = pwmRight;

cmd = struct();
cmd.err = err;
cmd.uUnsat = uUnsat;
cmd.uDiff = uDiff;
cmd.pwmLeft = pwmLeft;
cmd.pwmRight = pwmRight;
cmd.integral = state.integral;
cmd.dFilt = state.dFilt;
cmd.isSaturated = abs(uUnsat) > p.maxDiffPwm ...
    || pwmLeft <= p.minPwm || pwmLeft >= p.maxPwm ...
    || pwmRight <= p.minPwm || pwmRight >= p.maxPwm;
end
