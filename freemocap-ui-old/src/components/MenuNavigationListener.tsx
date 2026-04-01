import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Invisible component that listens for navigation events from the
 * native Electron menu (via the 'navigate' IPC channel) and forwards
 * them to react-router.
 *
 * Must be rendered inside a Router.
 */
export const MenuNavigationListener: React.FC = () => {
    const navigate = useNavigate();

    useEffect(() => {
        const electronAPI = (window as any).electronAPI;
        if (!electronAPI?.onNavigate) return;

        const cleanup = electronAPI.onNavigate((route: string) => {
            navigate(route);
        });

        return cleanup;
    }, [navigate]);

    return null;
};
