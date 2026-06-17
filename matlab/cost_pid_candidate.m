function cost = cost_pid_candidate(x, p)
%COST_PID_CANDIDATE Objective function used by PSO.
%
% The objective evaluates the same constrained, sampled controller path used
% for video and embedded-code bring-up: sensor noise, PWM saturation, slew
% limit, quantization, motor deadband, derivative filtering, and anti-windup.

if any(~isfinite(x)) || any(x < 0)
    cost = 1e12;
    return;
end

gains = struct('Kp', x(1), 'Ki', x(2), 'Kd', x(3));

try
    sim = simulate_noisy_pid_response(gains, p, false);
catch
    cost = 1e12;
    return;
end

err = deg2rad(sim.refDeg - sim.thetaDeg);
dt = [diff(sim.t); p.Ts];
uNorm = sim.uDiff / max(1, p.maxDiffPwm);

iae = sum(abs(err) .* dt);
ise = sum(err.^2 .* dt);
effort = sum(uNorm.^2 .* dt);
satFrac = mean(sim.isSaturated | abs(sim.uDiff) >= (0.98 * p.maxDiffPwm));
ratePenalty = sum((deg2rad(sim.thetaDotDegS) / 8).^2 .* dt);

maxAngle = max(abs(sim.thetaDeg));
if any(~isfinite(sim.thetaDeg)) || maxAngle > p.maxSafeAngleDeg
    cost = 1e9 + 1e7 * maxAngle;
    return;
end

finalError = abs(err(end));
sequenceProgressPenalty = 0;
if isfield(p, 'refSequenceDeg') && ~isempty(p.refSequenceDeg)
    finalTarget = p.refSequenceDeg(end);
    if abs(sim.refDeg(end) - finalTarget) > 0.1
        sequenceProgressPenalty = 100 + 10 * abs(sim.refDeg(end) - finalTarget);
    end
end

overshootPenalty = 0;
refs = unique(sim.refDeg, 'stable');
for i = 1:numel(refs)
    idx = sim.refDeg == refs(i);
    if any(idx)
        errDeg = sim.thetaDeg(idx) - refs(i);
        overshootPenalty = overshootPenalty + max(0, max(abs(errDeg)) - 8)^2;
    end
end

cost = 8.0 * iae ...
    + 2.0 * ise ...
    + 0.02 * effort ...
    + 4.0 * satFrac ...
    + 0.04 * ratePenalty ...
    + 20.0 * finalError^2 ...
    + 0.015 * overshootPenalty ...
    + sequenceProgressPenalty;
end

