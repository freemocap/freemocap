import {z} from 'zod';
import {CameraConfig} from "@/store";

// ==================== API Request/Response Types ====================
export interface PipelineConnectRequest {
    camera_configs?: string[];
}

export interface PipelineConnectResponse {
    camera_group_id: string;
    pipeline_id: string;
    camera_configs: Record<string, CameraConfig>;
}

// ==================== Pipeline State ====================
export interface PipelineState {
    cameraGroupId: string | null;
    pipelineId: string | null;
    isConnected: boolean;
    isLoading: boolean;
    error: string | null;
}


const RealtimePipelineConfigSchema = z.object({
    pipeline_id: z.string(),
    parameters: z.record(z.string(), z.any()),
})


export type RealtimePipelineConfig = z.infer<typeof RealtimePipelineConfigSchema>;
export interface ProcessingPipeline {
    id: string;
    name: string;
    isActive: boolean;
    config: RealtimePipelineConfig
}

export interface ProcessingPipelineState {
    pipelines: ProcessingPipeline[];
    isLoading: boolean;
    isActive: boolean;
    error: string | null;
}
