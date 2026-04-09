// src/hooks/useMenuActions.ts
import {useEffect} from 'react';
import {useNavigate} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {useAppDispatch, useAppSelector} from '@/store';
import {themeModeToggled} from '@/store/slices/theme';
import {camerasConnectOrUpdate, closeCameras, detectCameras, pauseUnpauseCameras} from '@/store/slices/cameras';
import {stopRecording} from '@/store/slices/recording';
import {selectVideoLoadFolder} from '@/store/slices/videos';
// import { localeChanged, selectLocale, localeToggled } from '@/store/slices/settings';
import {isElectron} from '@/services/electron-ipc/electron-ipc';
import {SUPPORTED_LOCALES} from '@/i18n';
import type {MenuAction} from '../../electron/main/services/menu-builder';

// i18n keys that the menu builder needs for translated labels
const MENU_LABEL_KEYS = [
    'menuFile',
    'menuView',
    'menuCamera',
    'menuRecording',
    'menuHelp',
    'menuDetectCameras',
    'menuConnectCameras',
    'menuCloseAllCameras',
    'menuOpenRecordingFolder',
    'menuToggleSidebar',
    'menuToggleTheme',
    'menuToggleFullScreen',
    'menuPauseUnpause',
    'menuConnectApplySettings',
    'menuCloseAll',
    'menuDocumentation',
    'menuGitHubRepository',
    'menuReportIssue',
    'menuAbout',
    'menuCheckForUpdates',
    'menuPlayback',
    'home',
    'cameras',
    'settings',
    'startRecording',
    'stopRecording',
    'language',
] as const;

// Build the locale entries array from the SUPPORTED_LOCALES config (once)
const LOCALE_ENTRIES = Object.entries(SUPPORTED_LOCALES).map(([code, { label }]) => ({
    code,
    label,
}));

interface UseMenuActionsParams {
    onToggleSidebar: () => void;
}

export function useMenuActions({ onToggleSidebar }: UseMenuActionsParams): void {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const { t, i18n } = useTranslation();

    const isRecording = useAppSelector((state) => state.recording.isRecording);
    // const currentLocale = useAppSelector(selectLocale);

    // Send translated menu labels + locale list to the main process whenever the language changes
    useEffect(() => {
        if (!isElectron() || !window.electronAPI?.sendMenuLabels) return;

        const labels: Record<string, string> = {};
        for (const key of MENU_LABEL_KEYS) {
            labels[key] = t(key);
        }
        window.electronAPI.sendMenuLabels({
            labels,
            locales: LOCALE_ENTRIES,
            // currentLocale,
        });
    }, [t, i18n.language]);//, currentLocale]);

    // Listen for menu actions dispatched from the native menu
    useEffect(() => {
        if (!isElectron() || !window.electronAPI?.onMenuAction) return;

        const cleanup = window.electronAPI.onMenuAction((action: string) => {
            // Handle locale change actions (dynamic pattern: "change-locale:xx")
            if (action.startsWith('change-locale:')) {
                const localeCode = action.slice('change-locale:'.length);
                // if (localeCode in SUPPORTED_LOCALES) {
                //     dispatch(localeChanged(localeCode as SupportedLocale));
                // }
                return;
            }

            const menuAction = action as MenuAction;

            switch (menuAction) {
                // Navigation
                case 'navigate-home':
                    navigate('/');
                    break;
                case 'navigate-cameras':
                    navigate('/cameras');
                    break;
                case 'navigate-playback':
                    navigate('/playback');
                    break;
                case 'navigate-settings':
                    navigate('/settings');
                    break;

                // View
                case 'toggle-theme':
                    dispatch(themeModeToggled());
                    break;
                case 'toggle-sidebar':
                    onToggleSidebar();
                    break;
                case 'toggle-fullscreen': {
                    if (document.fullscreenElement) {
                        document.exitFullscreen();
                    } else {
                        document.documentElement.requestFullscreen();
                    }
                    break;
                }

                // Camera actions
                case 'detect-cameras':
                    dispatch(detectCameras());
                    break;
                case 'connect-cameras':
                    dispatch(camerasConnectOrUpdate());
                    break;
                case 'close-cameras':
                    dispatch(closeCameras());
                    break;
                case 'pause-unpause-cameras':
                    dispatch(pauseUnpauseCameras());
                    break;

                // Locale toggle
                case 'toggle-locale':
                    // dispatch(localeToggled());
                    break;

                // Recording actions
                case 'start-recording':
                    if (!isRecording) {
                        navigate('/cameras');
                    }
                    break;
                case 'stop-recording':
                    if (isRecording) {
                        dispatch(stopRecording());
                    }
                    break;

                // Updates
                case 'check-for-updates':
                    window.dispatchEvent(new CustomEvent('check-for-updates'));
                    break;

                // File actions
                case 'open-recording-folder':
                    dispatch(selectVideoLoadFolder());
                    navigate('/playback');
                    break;
            }
        });

        return cleanup;
    }, [dispatch, navigate, isRecording, onToggleSidebar]);
}
