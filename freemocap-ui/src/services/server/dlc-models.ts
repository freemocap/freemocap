import {serverUrls} from '@/constants/server-urls';
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
async function request<T>(path: string, signal?: AbortSignal, body?: unknown): Promise<T> {
    const response = await fetch(`${serverUrls.getHttpUrl()}/freemocap/dlc/${path}`, {
        method: body === undefined ? 'GET' : 'POST', signal,
        ...(body === undefined ? {} : {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}),
    });
    if (!response.ok) throw new Error(await getDetailedErrorMessage(response));
    return response.json() as Promise<T>;
}
export const getDlcReadiness = (signal?: AbortSignal) => request<DlcReadiness>('readiness', signal);
export const inspectDlcModel = (sidecar_path: string, signal?: AbortSignal) => request<DlcModelMetadata>('inspect', signal, {sidecar_path});
export const importDlcModel = (body: DlcImportRequest, signal?: AbortSignal) => request<DlcImportJob>('import', signal, body);
export const getDlcImportJob = (jobId: string, signal?: AbortSignal) => request<DlcImportJob>(`import/${encodeURIComponent(jobId)}`, signal);
