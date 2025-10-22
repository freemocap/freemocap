import {useAppUrls} from "@/hooks/useAppUrls";

export const pauseUnpauseThunk = async () => {
    const pauseUnpauseUrl = useAppUrls.getHttpEndpointUrls().pauseUnpauseCameras;
    const response = await fetch(pauseUnpauseUrl, {method: 'GET'});

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response;
};
