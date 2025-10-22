import {urlService} from "@/config/appUrlService";

export const pauseUnpauseThunk = async () => {
    const pauseUnpauseUrl = urlService.getHttpEndpointUrls().pauseUnpauseCameras;
    const response = await fetch(pauseUnpauseUrl, {method: 'GET'});

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response;
};