import { useContext } from 'react';
import { AutoUpdateContext } from './AutoUpdateContext';

export function useAutoUpdate() {
    const ctx = useContext(AutoUpdateContext);
    if (!ctx) {
        throw new Error('useAutoUpdate must be used within an AutoUpdateProvider');
    }
    return ctx;
}
