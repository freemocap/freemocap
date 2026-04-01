import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSetupWizardRequired } from '@/components/setup-wizard/SetupWizard';

/**
 * Invisible component that redirects to /setup on first launch.
 * Render this anywhere inside a HashRouter.
 * Once setup is complete (persisted to ~/.freemocap/settings.json),
 * this does nothing.
 */
export const FirstLaunchRedirect: React.FC = () => {
    const { loading, required } = useSetupWizardRequired();
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
        if (loading) return;
        if (!required) return;
        // Don't redirect if we're already on the settings page
        if (location.pathname === '/settings') return;

        navigate('/settings', { replace: true });
    }, [loading, required, location.pathname, navigate]);

    return null;
};
