function omega = pwm_to_omega(pwm, p)
%PWM_TO_OMEGA Ideal ESC command map from PWM microseconds to motor speed.
%
% The ESC is modeled as ideal and linear: PWM maps directly to throttle.
% Motor and propeller inertia are still represented by tauMotor in the plant.

pwmEff = pwm;
pwmEff(pwmEff < p.motorDeadbandPwm) = p.minPwm;
throttle = (pwmEff - p.minPwm) ./ max(1, p.maxPwm - p.minPwm);
throttle = min(max(throttle, 0), 1);
omega = p.maxOmega .* throttle;
end

