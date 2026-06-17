function videoFile = export_1dof_copter_video(sim, p, videoFile)
%EXPORT_1DOF_COPTER_VIDEO Render the 1-DOF copter simulation to MP4.

if nargin < 2
    p = init_1dof_params();
end
if nargin < 1 || isempty(sim)
    if exist(fullfile('output', 'tuned_pid_gains.mat'), 'file')
        data = load(fullfile('output', 'tuned_pid_gains.mat'), 'gains');
        gains = data.gains;
    else
        gains = struct('Kp', 25, 'Ki', 5, 'Kd', 4);
    end
    sim = simulate_noisy_pid_response(gains, p);
end
if nargin < 3 || isempty(videoFile)
    if ~exist('output', 'dir')
        mkdir('output');
    end
    videoFile = fullfile('output', 'one_dof_copter_sim.mp4');
end

writer = VideoWriter(videoFile, 'MPEG-4');
if isfield(p, 'videoFrameRate') && ~isempty(p.videoFrameRate)
    writer.FrameRate = p.videoFrameRate;
else
    writer.FrameRate = 30;
end
writer.Quality = 95;
open(writer);
cleanup = onCleanup(@() close(writer));

fig = figure('Name', '1-DOF Copter Animation', ...
    'Color', 'w', 'Position', [100 100 1280 720], 'Visible', 'off');

frameStride = max(1, round(1 / (writer.FrameRate * p.Ts)));
thetaRad = deg2rad(sim.thetaDeg);
refDeg = p.refDeg * ones(size(sim.t));
if isfield(sim, 'refDeg')
    refDeg = sim.refDeg;
end

for k = 1:frameStride:numel(sim.t)
    clf(fig);
    tl = tiledlayout(fig, 2, 2, 'TileSpacing', 'compact', 'Padding', 'compact');

    axRig = nexttile(tl, 1, [2 1]);
    hold(axRig, 'on');
    axis(axRig, 'equal');
    grid(axRig, 'on');
    xlim(axRig, [-p.L1 - 0.16, p.L2 + 0.16]);
    ylim(axRig, [-0.30, 0.30]);
    xlabel(axRig, 'x (m)');
    ylabel(axRig, 'y (m)');
    title(axRig, sprintf('1-DOF Copter  t = %.2f s', sim.t(k)));

    th = thetaRad(k);
    left = [-p.L1 * cos(th), -p.L1 * sin(th)];
    right = [p.L2 * cos(th), p.L2 * sin(th)];

    plot(axRig, [0 0], [-0.28 0], 'k-', 'LineWidth', 5);
    plot(axRig, [-0.08 0.08], [-0.28 -0.28], 'k-', 'LineWidth', 8);
    plot(axRig, [left(1) right(1)], [left(2) right(2)], ...
        'Color', [0.15 0.15 0.15], 'LineWidth', 8);
    plot(axRig, 0, 0, 'ko', 'MarkerFaceColor', [0.8 0.8 0.8], 'MarkerSize', 12);

    draw_motor(axRig, left, th, sim.pwmLeft(k), p, 'left');
    draw_motor(axRig, right, th, sim.pwmRight(k), p, 'right');

    angleColor = [0.1 0.45 0.85];
    if abs(sim.thetaDeg(k)) > 0.8 * p.maxSafeAngleDeg
        angleColor = [0.85 0.15 0.12];
    end
    text(axRig, -p.L1, 0.26, sprintf('\\theta = %.2f deg', sim.thetaDeg(k)), ...
        'FontSize', 14, 'FontWeight', 'bold', 'Color', angleColor);
    text(axRig, -p.L1, 0.22, sprintf('reference = %.2f deg', refDeg(k)), ...
        'FontSize', 11);

    axTheta = nexttile(tl, 2);
    plot(axTheta, sim.t(1:k), sim.thetaDeg(1:k), 'LineWidth', 1.6);
    hold(axTheta, 'on');
    stairs(axTheta, sim.t(1:k), refDeg(1:k), '--', 'LineWidth', 1.3);
    yline(axTheta, p.maxSafeAngleDeg, ':r');
    yline(axTheta, -p.maxSafeAngleDeg, ':r');
    grid(axTheta, 'on');
    xlim(axTheta, [0 sim.t(end)]);
    ylim(axTheta, [-p.maxSafeAngleDeg-5 p.maxSafeAngleDeg+5]);
    ylabel(axTheta, 'theta (deg)');
    title(axTheta, 'Angle Tracking');

    axPwm = nexttile(tl, 4);
    bar(axPwm, [1 2], [sim.pwmLeft(k), sim.pwmRight(k)], 0.5);
    hold(axPwm, 'on');
    yline(axPwm, p.hoverPwm, '--');
    ylim(axPwm, [p.minPwm p.maxPwm]);
    xlim(axPwm, [0.3 2.7]);
    set(axPwm, 'XTick', [1 2], 'XTickLabel', {'Left', 'Right'});
    ylabel(axPwm, 'PWM (us)');
    title(axPwm, sprintf('u_{diff} = %.1f us', sim.uDiff(k)));
    grid(axPwm, 'on');
    if isfield(sim, 'isSaturated') && sim.isSaturated(k)
        text(axPwm, 1.5, p.maxPwm - 60, 'SATURATION / AW ACTIVE', ...
            'HorizontalAlignment', 'center', 'Color', [0.8 0.1 0.1], ...
            'FontWeight', 'bold');
    end

    writeVideo(writer, getframe(fig));
end

fprintf('Saved video: %s\n', videoFile);
end

function draw_motor(ax, pos, theta, pwm, p, labelText)
armNormal = [-sin(theta), cos(theta)];
throttle = (pwm - p.minPwm) / max(1, p.maxPwm - p.minPwm);
throttle = min(max(throttle, 0), 1);
discRadius = 0.035 + 0.025 * throttle;

plot(ax, pos(1), pos(2), 'o', 'MarkerSize', 16, ...
    'MarkerFaceColor', [0.2 0.2 0.2], 'MarkerEdgeColor', 'none');
rectangle(ax, 'Position', [pos(1)-discRadius, pos(2)-discRadius, ...
    2*discRadius, 2*discRadius], 'Curvature', [1 1], ...
    'EdgeColor', [0.1 0.65 0.25], 'LineWidth', 1.8);
quiver(ax, pos(1), pos(2), 0.08 * throttle * armNormal(1), ...
    0.08 * throttle * armNormal(2), 0, 'LineWidth', 2, ...
    'Color', [0.1 0.65 0.25], 'MaxHeadSize', 2.5);
text(ax, pos(1), pos(2) - 0.07, sprintf('%s\n%d us', labelText, round(pwm)), ...
    'HorizontalAlignment', 'center', 'FontSize', 9);
end
