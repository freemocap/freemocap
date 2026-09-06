# Pipeline lifecycle scopes

Current task/mode scopes are mocap/realtime, mocap/posthoc and calibration/posthoc.
Calibration/realtime is not implemented. Synchronization is a separate posthoc job.

## Cancellation API

All routes below have the `/freemocap` prefix. DELETE on a collection cancels only that scope;
DELETE with an ID rejects IDs belonging to another scope without modifying any job.

- `/mocap/realtime/pipelines` and `/mocap/realtime/pipelines/{pipeline_id}`
- `/mocap/posthoc/pipelines` and `/mocap/posthoc/pipelines/{pipeline_id}`
- `/calibration/posthoc/pipelines` and `/calibration/posthoc/pipelines/{pipeline_id}`
- `/mocap/synchronization/jobs/{job_id}`

The frontend's Stop all posthoc jobs action snapshots its active job IDs and calls the relevant
scoped endpoint for each. Individual successes update only those jobs; failed requests remain
visible as cancellation errors. Realtime processing and camera capture are independent of this action.

## Worker ownership

SkellyCam's WorkerRegistry creates each worker with an explicit owner shutdown flag and worker mode.
FreeMoCap passes its PipelineIPC shutdown flag; camera acquisition passes its CameraGroupIPC flag.
Process/thread exceptions and process termination signals affect that owner, not the application.
The registry detects nonzero exits, including abrupt native-process exits, records failure, signals
the owner and terminates its remaining workers. Process and thread workers share the registry.

Intentional shutdown marks workers before signaling them. Pipeline teardown stops workers before
closing queues. Posthoc progress reports worker failure even if no terminal message survived the
crash; failure takes precedence over a queued completion. Realtime application state includes its
worker failure detail. The application kill flag remains reserved for explicit application shutdown
and parent-heartbeat failure.

Threads must cooperate with shutdown; Python cannot safely force-kill an unresponsive thread.
ManagedWorker raises if termination cannot complete rather than killing the application.

## Validation and handoff

50 focused tests pass: scoped HTTP cancellation, wrong-task rejection, failure progress, recording
regressions, worker lifecycle, process/thread exceptions and abrupt process exit with unrelated
workers remaining alive. Frontend TypeScript checking and Python lint pass.

The FreeMoCap virtual environment currently uses editable local SkellyCam. Until the dependency pin
includes these SkellyCam changes, launch with `uv run --no-sync freemocap` from the FreeMoCap repo.
Do not let dependency synchronization replace the edited worker package during acceptance testing.

Real-app acceptance remains: run realtime tracking alongside posthoc mocap/calibration; stop
realtime and verify posthoc continues. Start both posthoc task types; cancel one and verify the other
continues. Verify normal app shutdown still closes all processing and camera workers.

Next refactor topic: processing request/preflight at the mocap API boundary. Lifecycle changes do
not implement stage-selective processing or calibration/realtime.
