%MAIN Run the 1-DOF copter simulation and export an animation video.
%
% This entry point can be launched from the repository root or from another
% MATLAB working folder. It loads the model parameters, reuses tuned PID gains
% when available, runs the realistic sampled simulation, and saves an MP4 video
% under matlab/output.

clearvars;
close all;
clc;

projectRoot = fileparts(mfilename('fullpath'));
matlabDir = fullfile(projectRoot, 'matlab');
outputDir = fullfile(matlabDir, 'output');

addpath(genpath(matlabDir));

if ~exist(outputDir, 'dir')
    mkdir(outputDir);
end

p = init_1dof_params();
p.simTime = 12.0;
p.videoFrameRate = 12;

gainFile = fullfile(outputDir, 'tuned_pid_gains.mat');
gainJsonFile = fullfile(outputDir, 'tuned_pid_gains.json');
if exist(gainFile, 'file')
    gainData = load(gainFile, 'gains');
    gains = gainData.gains;
    fprintf('Loaded tuned gains from %s\n', gainFile);
elseif exist(gainJsonFile, 'file')
    gainData = jsondecode(fileread(gainJsonFile));
    gains = struct('Kp', gainData.Kp, 'Ki', gainData.Ki, 'Kd', gainData.Kd);
    fprintf('Loaded tuned gains from %s\n', gainJsonFile);
else
    fprintf('Tuned gains not found. Running PSO PID autotune first...\n');
    previousFolder = pwd;
    cleanup = onCleanup(@() cd(previousFolder));
    cd(matlabDir);
    tuneResult = run_pso_pid_autotune(p);
    gains = tuneResult.gains;
    clear cleanup;
end

fprintf('Simulating 1-DOF copter motion...\n');
sim = simulate_noisy_pid_response(gains, p, false);

videoFile = fullfile(outputDir, 'one_dof_copter_motion.mp4');
if exist(videoFile, 'file')
    delete(videoFile);
end
fprintf('Exporting animation video...\n');
export_1dof_copter_video(sim, p, videoFile);

fprintf('\nDone.\nVideo saved to:\n%s\n', videoFile);
