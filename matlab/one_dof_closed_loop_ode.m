function [dx, aux] = one_dof_closed_loop_ode(t, x, gains, p)
%ONE_DOF_CLOSED_LOOP_ODE Nonlinear closed-loop 1-DOF copter dynamics.
%
% State vector:
% x(1) theta, rad
% x(2) thetaDot, rad/s
% x(3) omegaLeft, rad/s
% x(4) omegaRight, rad/s
% x(5) integral error
% x(6) filtered thetaDot for derivative-on-measurement

theta = x(1);
thetaDot = x(2);
omegaLeft = max(0, x(3));
omegaRight = max(0, x(4));
intE = x(5);
dFilt = x(6);

thetaRef = deg2rad(p.refDeg);
err = thetaRef - theta;

dFiltDot = (thetaDot - dFilt) / max(p.derivativeTau, eps);

uRaw = gains.Kp * err + gains.Ki * intE - gains.Kd * dFilt;
uDiff = min(max(uRaw, -p.maxDiffPwm), p.maxDiffPwm);

% Conditional integration anti-windup.
isHighSat = uRaw > p.maxDiffPwm && err > 0;
isLowSat = uRaw < -p.maxDiffPwm && err < 0;
if isHighSat || isLowSat
    intDot = 0;
else
    intDot = err;
end

if gains.Ki > eps
    intLimit = p.integratorLimit / gains.Ki;
    if (intE >= intLimit && intDot > 0) || (intE <= -intLimit && intDot < 0)
        intDot = 0;
    end
end

pwmLeft = min(max(p.hoverPwm - uDiff, p.minPwm), p.maxPwm);
pwmRight = min(max(p.hoverPwm + uDiff, p.minPwm), p.maxPwm);

omegaCmdLeft = pwm_to_omega(pwmLeft, p);
omegaCmdRight = pwm_to_omega(pwmRight, p);

omegaLeftDot = (omegaCmdLeft - omegaLeft) / p.tauMotor;
omegaRightDot = (omegaCmdRight - omegaRight) / p.tauMotor;

tauLeft = p.L1 * p.kf * omegaLeft^2;
tauRight = p.L2 * p.kf * omegaRight^2;
tauDist = 0;
if t >= p.disturbanceTime
    tauDist = p.disturbanceTorque;
end

thetaDDot = (tauRight - tauLeft + tauDist ...
    - p.c * thetaDot - p.mgl * sin(theta)) / p.J;

dx = [thetaDot; thetaDDot; omegaLeftDot; omegaRightDot; intDot; dFiltDot];

aux = struct();
aux.err = err;
aux.uRaw = uRaw;
aux.uDiff = uDiff;
aux.pwmLeft = pwmLeft;
aux.pwmRight = pwmRight;
aux.tauLeft = tauLeft;
aux.tauRight = tauRight;
aux.tauDist = tauDist;
end
