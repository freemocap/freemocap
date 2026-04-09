import {useEffect, useState} from 'react';
import {useElectronIPC} from '@/services';

export function useAppVersion(): string | null {
    const [version, setVersion] = useState<string | null>(null);
    const { isElectron, api } = useElectronIPC();

    useEffect(() => {
        if (!isElectron || !api) return;

        api.app.getVersion.query().then((v) => {
            setVersion(v);
        }).catch((err) => {
            console.error('Failed to get app version:', err);
        });
    }, [isElectron, api]);

    return version;
}
