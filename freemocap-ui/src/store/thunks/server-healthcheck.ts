import {useAppUrls} from "@/hooks/useAppUrls";

export const serverHealthcheck = async () => {
    const url = useAppUrls.getHttpEndpointUrls().health;
    const response = await fetch(url, {method: 'GET'});

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response;
};
