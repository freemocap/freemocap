import {serverClient} from '@/services/server/sdk';
import {getDetailedErrorMessage} from '@/store/slices/thunk-helpers';

export interface DlcModelMetadata {
    model_name: string;
    sidecar_path: string;
    model_sha256: string;
    input_size: [number, number];
    resize_method: string;
    keypoint_names: string[];
    connections: [string, string][];
    precision: 'fp32';
}
export interface DlcReadiness {available: boolean; supported_model: string; missing_packages: string[]; detail: string}
export interface DlcImportRequest {
    pose_config_path: string;
    checkpoint_path: string;
    project_config_path?: string | null;
    image_height: number;
    image_width: number;
}
export interface DlcImportJob {
    job_id: string;
    status: 'queued' | 'running' | 'complete' | 'failed';
    detail: string;
    result: DlcModelMetadata | null;
}
async function request<T>(pending: Promise<Response>): Promise<T> {
    const response = await pending;
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return response.json() as Promise<T>;
}
export const getDlcReadiness = (signal?: AbortSignal) => request<DlcReadiness>(
    serverClient().responses.conversion_readiness_freemocap_dlc_readiness_get({signal}));
export const inspectDlcModel = (sidecar_path: string, signal?: AbortSignal) => request<DlcModelMetadata>(
    serverClient().responses.inspect_model_freemocap_dlc_inspect_post({signal, body: {sidecar_path}}));
export const importDlcModel = (body: DlcImportRequest, signal?: AbortSignal) => request<DlcImportJob>(
    serverClient().responses.import_model_freemocap_dlc_import_post({signal, body}));
export const getDlcImportJob = (jobId: string, signal?: AbortSignal) => request<DlcImportJob>(
    serverClient().responses.import_status_freemocap_dlc_import__job_id__get({signal, path: {job_id: jobId}}));
