function result = run_pso_pid_autotune(p)
%RUN_PSO_PID_AUTOTUNE Tune PID gains for the 1-DOF copter using PSO.
%
% result = run_pso_pid_autotune()
% result = run_pso_pid_autotune(p)

if nargin < 1
    p = init_1dof_params();
end

rng(p.psoSeed);

bounds = [p.KpBounds; p.KiBounds; p.KdBounds];
nVar = size(bounds, 1);
nParticles = p.psoParticles;
nIterations = p.psoIterations;

span = bounds(:, 2)' - bounds(:, 1)';
pos = bounds(:, 1)' + rand(nParticles, nVar) .* span;
vel = zeros(nParticles, nVar);

pbestPos = pos;
pbestCost = inf(nParticles, 1);
gbestPos = pos(1, :);
gbestCost = inf;
history = zeros(nIterations, 1);

wMax = 0.86;
wMin = 0.42;
c1 = 1.55;
c2 = 1.65;
vMax = 0.22 .* span;

fprintf('Starting PSO PID tuning with %d particles for %d iterations...\n', ...
    nParticles, nIterations);

for iter = 1:nIterations
    inertia = wMax - (wMax - wMin) * (iter - 1) / max(1, nIterations - 1);

    for i = 1:nParticles
        cost = cost_pid_candidate(pos(i, :), p);
        if cost < pbestCost(i)
            pbestCost(i) = cost;
            pbestPos(i, :) = pos(i, :);
        end
        if cost < gbestCost
            gbestCost = cost;
            gbestPos = pos(i, :);
        end
    end

    r1 = rand(nParticles, nVar);
    r2 = rand(nParticles, nVar);
    vel = inertia .* vel ...
        + c1 .* r1 .* (pbestPos - pos) ...
        + c2 .* r2 .* (gbestPos - pos);
    vel = min(max(vel, -vMax), vMax);

    pos = pos + vel;
    pos = min(max(pos, bounds(:, 1)'), bounds(:, 2)');

    history(iter) = gbestCost;
    fprintf('iter %03d/%03d  cost %.6g  Kp %.4f  Ki %.4f  Kd %.4f\n', ...
        iter, nIterations, gbestCost, gbestPos(1), gbestPos(2), gbestPos(3));
end

gains = struct('Kp', gbestPos(1), 'Ki', gbestPos(2), 'Kd', gbestPos(3));

result = struct();
result.gains = gains;
result.bestCost = gbestCost;
result.history = history;
result.params = p;

if ~exist('output', 'dir')
    mkdir('output');
end

save(fullfile('output', 'tuned_pid_gains.mat'), 'gains', 'result');
write_gains_json(fullfile('output', 'tuned_pid_gains.json'), gains, gbestCost, p);

fprintf('\nBest gains:\n');
fprintf('Kp = %.8g\nKi = %.8g\nKd = %.8g\nCost = %.8g\n', ...
    gains.Kp, gains.Ki, gains.Kd, gbestCost);
fprintf('Saved output/tuned_pid_gains.mat and output/tuned_pid_gains.json\n');
end

function write_gains_json(fileName, gains, bestCost, p)
fid = fopen(fileName, 'w');
if fid < 0
    warning('Could not write %s', fileName);
    return;
end
cleanup = onCleanup(@() fclose(fid));
fprintf(fid, '{\n');
fprintf(fid, '  "Kp": %.12g,\n', gains.Kp);
fprintf(fid, '  "Ki": %.12g,\n', gains.Ki);
fprintf(fid, '  "Kd": %.12g,\n', gains.Kd);
fprintf(fid, '  "bestCost": %.12g,\n', bestCost);
fprintf(fid, '  "sampleTime": %.12g,\n', p.Ts);
fprintf(fid, '  "referenceDegrees": %.12g\n', p.refDeg);
fprintf(fid, '}\n');
end

