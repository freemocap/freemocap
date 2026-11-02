import {recordingLocationFromPath} from '../recording/recording-location';
import {createHttpClient, type ResourceOptions} from '@freemocap/client/http';
import {serverUrls} from '@/constants/server-urls';

/** UI configuration chooses the server; the SDK owns HTTP serialization. */
export function serverClient() {
    return createHttpClient({baseUrl: serverUrls.getHttpUrl()});
}

/** Resources carry their server origin so this also works inside playback workers. */
export function serverResourceResponse(resource: string | URL, options?: ResourceOptions): Promise<Response> {
    const url = new URL(resource);
    return createHttpClient({baseUrl: url.origin}).assetResponse(url.pathname + url.search, options);
}

export function recordingRequest(folder: string) {
    const location = recordingLocationFromPath(folder);
    return {path: {recording_id: location.recordingId},
        query: {recording_parent_directory: location.recordingParentDirectory}};
}
