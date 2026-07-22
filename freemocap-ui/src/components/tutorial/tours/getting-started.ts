import type {Tour} from '../types';
import {EXTERNAL_URLS} from '@/constants/external-urls';

// v1 getting-started tour — the main "first touch" path a new user follows:
//   welcome → server connection → camera connection → realtime pipeline
//         → calibration (with a docs hand-off) → record mocap → finish
//
// All pointer steps live on the /streaming view. The engine also supports
// branching (see TourStep.choices) — this tour just runs linearly for now. Deeper
// per-topic tutorials can be added later as their own tours in the registry.
export const gettingStartedTour: Tour = {
    id: 'getting-started',
    startStepId: 'welcome',
    steps: {
        welcome: {
            id: 'welcome',
            kind: 'info',
            titleKey: 'tour.welcome.title',
            textKey: 'tour.welcome.text',
            choices: [
                {id: 'start', labelKey: 'tour.welcome.start', next: 'server-connection'},
            ],
        },

        'server-connection': {
            id: 'server-connection',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="connection:server-connection"]',
            position: 'pos-bottom-right',
            titleKey: 'tour.server.title',
            textKey: 'tour.server.text',
            deeper: 'server-connection.1',
            next: 'camera-connection',
        },
        // ── Server-connection sub-tour (steps 2.1, 2.2) — rejoins the main path at
        //    camera-connection. A sub-step just sets parentStepId + chains via next.
        'server-connection.1': {
            id: 'server-connection.1',
            parentStepId: 'server-connection',
            kind: 'pointer',
            route: '/streaming',
            target: '.connection-container',
            position: 'pos-right',
            offsetTop: 150,
            // Open the connection panel so the sub-tour can point at its innards.
            // The dropdown closes on the next outside click, so each sub-step reopens it.
            onEnter: {
                type: 'click',
                target: '[data-onboarding="connection:server-connection"] .connection-status-button-opener',
                unlessVisible: '.connection-container',
            },
            onExit: {
                type: 'click',
                target: '[data-onboarding="connection:server-connection"] .connection-status-button-opener',
                onlyIfVisible: '.connection-container',
            },
            titleKey: 'tour.serverDeep.status.title',
            textKey: 'tour.serverDeep.status.text',
            next: 'server-connection.2',
        },
        'server-connection.2': {
            id: 'server-connection.2',
            parentStepId: 'server-connection',
            kind: 'pointer',
            route: '/streaming',
            target: '.connection-container',
            position: 'pos-right',
            offsetTop: 150,
            onEnter: {
                type: 'click',
                target: '[data-onboarding="connection:server-connection"] .connection-status-button-opener',
                unlessVisible: '.connection-container',
            },
            onExit: {
                type: 'click',
                target: '[data-onboarding="connection:server-connection"] .connection-status-button-opener',
                onlyIfVisible: '.connection-container',
            },
            titleKey: 'tour.serverDeep.toggle.title',
            textKey: 'tour.serverDeep.toggle.text',
            next: 'camera-connection',
        },
        'camera-connection': {
            id: 'camera-connection',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="camera:connect-camera"]',
            position: 'pos-bottom-left',
            titleKey: 'tour.camera.title',
            textKey: 'tour.camera.text',
            deeper: 'camera-connection.1',
            next: 'realtime-pipeline',
        },
        // ── Camera-connection sub-tour (steps 3.1, 3.2) — rejoins at realtime-pipeline.
        'camera-connection.1': {
            id: 'camera-connection.1',
            parentStepId: 'camera-connection',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="camera:connect-camera"]',
            position: 'pos-bottom-left',
            titleKey: 'tour.cameraDeep.detect.title',
            textKey: 'tour.cameraDeep.detect.text',
            next: 'camera-connection.2',
        },
        'camera-connection.2': {
            id: 'camera-connection.2',
            parentStepId: 'camera-connection',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="camera:connect-camera"]',
            position: 'pos-bottom-left',
            titleKey: 'tour.cameraDeep.settings.title',
            textKey: 'tour.cameraDeep.settings.text',
            next: 'realtime-pipeline',
        },
        'realtime-pipeline': {
            id: 'realtime-pipeline',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="realtime:pipeline"]',
            position: 'pos-bottom-right',
            titleKey: 'tour.realtime.title',
            textKey: 'tour.realtime.text',
            next: 'calibration',
        },
        calibration: {
            id: 'calibration',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="calibration:what-is-calibration"]',
            position: 'pos-bottom-left',
            titleKey: 'tour.calibration.title',
            textKey: 'tour.calibration.text',
            docsUrl: EXTERNAL_URLS.DOCS,
            next: 'recording',
        },
        recording: {
            id: 'recording',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="recording:start-recording"]',
            position: 'pos-top-left',
            titleKey: 'tour.recording.title',
            textKey: 'tour.recording.text',
            next: 'nav-tabs',
        },
        'nav-tabs': {
            id: 'nav-tabs',
            kind: 'pointer',
            route: '/streaming',
            target: '[data-onboarding="nav:tabs"]',
            position: 'pos-bottom-left',
            titleKey: 'tour.tabs.title',
            textKey: 'tour.tabs.text',
            next: 'finish',
        },
        finish: {
            id: 'finish',
            kind: 'info',
            titleKey: 'tour.finish.title',
            textKey: 'tour.finish.text',
            choices: [
                {id: 'done', labelKey: 'tour.finish.done', next: ''},
            ],
        },
    },
};
