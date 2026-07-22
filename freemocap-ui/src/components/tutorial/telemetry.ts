import {serverUrls} from '@/constants/server-urls';

// Tour lifecycle events form a funnel so we can see WHERE people drop off, not
// just how many finish:
//   tour_started → tour_step_viewed (once per step) → tour_completed | tour_skipped
// The step id on tour_skipped is the most actionable signal — it's the exact step
// people abandon on.
export type TourEvent =
    | 'tour_started'
    | 'tour_step_viewed'
    | 'tour_deeper'
    | 'tour_completed'
    | 'tour_skipped';

// Fire-and-forget. Telemetry is best-effort instrumentation at a system boundary:
// it must never disrupt the tour, so network/serialization failures are swallowed.
// The backend no-ops when the user has opted out (see /freemocap/telemetry/track),
// so the opt-in decision stays in one place and we don't re-check it here.
export function emitTourEvent(event: TourEvent, payload: Record<string, unknown>): void {
    try {
        void fetch(serverUrls.endpoints.trackTelemetry, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({eventType: event, payload}),
            keepalive: true, // let the event flush even if a route change unmounts us
        }).catch(() => {});
    } catch {
        // ignore — telemetry must never break the tour
    }
}
