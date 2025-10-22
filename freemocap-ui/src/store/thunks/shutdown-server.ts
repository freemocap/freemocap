import {useAppUrls} from "@/hooks/useAppUrls";

export const shutdownServer = async () => {
    const url = useAppUrls.getHttpEndpointUrls().shutdown;
    const response = await fetch(url, {method: 'GET'});

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response;
};
