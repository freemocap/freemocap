import {z} from 'zod';
import {serverClient, recordingRequest} from '@/services/server/sdk';
import {ProcessingPlanSchema, type ProcessingPlan} from '@/services/server/transport/message-contract';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

const PlanPreviewSchema = z.object({
    plan: ProcessingPlanSchema.nullable(),
    errors: z.array(z.string()),
});

/** The server's answer to "what would Process run": a plan, or the reasons it cannot run. */
export type PlanPreview = z.infer<typeof PlanPreviewSchema>;
export type {ProcessingPlan};

/** Ask the server for the graph it would run for this recording and configuration, without running it. */
export async function previewProcessingPlan(path: string, config: Record<string, unknown>, signal: AbortSignal): Promise<PlanPreview> {
    const response = await serverClient().responses.preview_mocap_plan_freemocap_recordings__recording_id__processing_plan_post({
        ...recordingRequest(path), signal,
        headers: {'Content-Type': 'application/json'},
        body: {kind: 'mocap', config} as never,
    });
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return PlanPreviewSchema.parse(await response.json());
}
