function sim = simulate_pid_response(gains, p)
%SIMULATE_PID_RESPONSE Plot closed-loop response for selected PID gains.

if nargin < 2
    p = init_1dof_params();
end
if nargin < 1 || isempty(gains)
    data = load(fullfile('output', 'tuned_pid_gains.mat'), 'gains');
    gains = data.gains;
end

tSpan = 0:p.Ts:p.simTime;
x0 = zeros(6, 1);
x0(1) = deg2rad(p.theta0Deg);
x0(3) = pwm_to_omega(p.hoverPwm, p);
x0(4) = pwm_to_omega(p.hoverPwm, p);

opts = odeset('RelTol', 1e-5, 'AbsTol', 1e-7);
[t, y] = ode45(@(t, xState) one_dof_closed_loop_ode(t, xState, gains, p), ...
    tSpan, x0, opts);

uDiff = zeros(size(t));
pwmLeft = zeros(size(t));
pwmRight = zeros(size(t));
for k = 1:numel(t)
    [~, aux] = one_dof_closed_loop_ode(t(k), y(k, :)', gains, p);
    uDiff(k) = aux.uDiff;
    pwmLeft(k) = aux.pwmLeft;
    pwmRight(k) = aux.pwmRight;
end

sim = struct();
sim.t = t;
sim.thetaDeg = rad2deg(y(:, 1));
sim.thetaDotDeg = rad2deg(y(:, 2));
sim.uDiff = uDiff;
sim.pwmLeft = pwmLeft;
sim.pwmRight = pwmRight;

figure('Name', '1-DOF Copter PID Response');
tiledlayout(3, 1);

nexttile;
plot(t, sim.thetaDeg, 'LineWidth', 1.5);
hold on;
yline(p.refDeg, '--');
grid on;
ylabel('theta (deg)');
title(sprintf('PSO PID: Kp %.3g, Ki %.3g, Kd %.3g', ...
    gains.Kp, gains.Ki, gains.Kd));

nexttile;
plot(t, uDiff, 'LineWidth', 1.5);
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
