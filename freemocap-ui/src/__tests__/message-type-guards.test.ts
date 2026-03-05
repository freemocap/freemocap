import { describe, it, expect } from 'vitest';
import {
    isSettingsStateMessage,
    isLogRecord,
    isFramerateUpdate,
} from '@/services/server/server-helpers/websocket-message-types';

// ---------------------------------------------------------------------------
// isSettingsStateMessage
// ---------------------------------------------------------------------------

describe('isSettingsStateMessage', () => {
    it('returns true for valid settings/state message', () => {
        const msg = {
            message_type: 'settings/state',
            settings: {
                cameras: {},
                pipeline: {},
                calibration: {},
                mocap: {},
            },
            version: 1,
        };
        expect(isSettingsStateMessage(msg)).toBe(true);
    });

    it('returns false if message_type is wrong', () => {
        const msg = {
            message_type: 'settings/patch',
            settings: {},
            version: 1,
        };
        expect(isSettingsStateMessage(msg)).toBe(false);
    });

    it('returns false if message_type is missing', () => {
        const msg = {
            settings: {},
            version: 1,
        };
        expect(isSettingsStateMessage(msg)).toBe(false);
    });

    it('returns false if settings is missing', () => {
        const msg = {
            message_type: 'settings/state',
            version: 1,
        };
        expect(isSettingsStateMessage(msg)).toBe(false);
    });

    it('returns false if settings is null', () => {
        const msg = {
            message_type: 'settings/state',
            settings: null,
            version: 1,
        };
        expect(isSettingsStateMessage(msg)).toBe(false);
    });

    it('returns false if version is missing', () => {
        const msg = {
            message_type: 'settings/state',
            settings: {},
        };
        expect(isSettingsStateMessage(msg)).toBe(false);
    });

    it('returns false if version is not a number', () => {
        const msg = {
            message_type: 'settings/state',
            settings: {},
            version: '1',
        };
        expect(isSettingsStateMessage(msg)).toBe(false);
    });

    it('returns false for null', () => {
        expect(isSettingsStateMessage(null)).toBe(false);
    });

    it('returns false for undefined', () => {
        expect(isSettingsStateMessage(undefined)).toBe(false);
    });

    it('returns false for a string', () => {
        expect(isSettingsStateMessage('hello')).toBe(false);
    });

    it('returns false for a number', () => {
        expect(isSettingsStateMessage(42)).toBe(false);
    });

    it('returns false for an empty object', () => {
        expect(isSettingsStateMessage({})).toBe(false);
    });
});

// ---------------------------------------------------------------------------
// isLogRecord
// ---------------------------------------------------------------------------

describe('isLogRecord', () => {
    it('returns true for valid log record', () => {
        const msg = {
            message_type: 'log_record',
            levelname: 'INFO',
            message: 'Something happened',
            levelno: 20,
        };
        expect(isLogRecord(msg)).toBe(true);
    });

    it('returns false if message_type is wrong', () => {
        const msg = {
            message_type: 'not_log',
            levelname: 'INFO',
            message: 'nope',
        };
        expect(isLogRecord(msg)).toBe(false);
    });

    it('returns false if levelname missing', () => {
        const msg = {
            message_type: 'log_record',
            message: 'no level',
        };
        expect(isLogRecord(msg)).toBe(false);
    });

    it('returns false if message missing', () => {
        const msg = {
            message_type: 'log_record',
            levelname: 'INFO',
        };
        expect(isLogRecord(msg)).toBe(false);
    });

    it('returns false for null', () => {
        expect(isLogRecord(null)).toBe(false);
    });
});

// ---------------------------------------------------------------------------
// isFramerateUpdate
// ---------------------------------------------------------------------------

describe('isFramerateUpdate', () => {
    it('returns true for valid framerate update', () => {
        const msg = {
            message_type: 'framerate_update',
            camera_group_id: 'group-0',
            backend_framerate: { fps: 30 },
            frontend_framerate: { fps: 28 },
        };
        expect(isFramerateUpdate(msg)).toBe(true);
    });

    it('returns false if message_type is wrong', () => {
        const msg = {
            message_type: 'not_framerate',
            camera_group_id: 'group-0',
            backend_framerate: {},
            frontend_framerate: {},
        };
        expect(isFramerateUpdate(msg)).toBe(false);
    });

    it('returns false if camera_group_id missing', () => {
        const msg = {
            message_type: 'framerate_update',
            backend_framerate: {},
            frontend_framerate: {},
        };
        expect(isFramerateUpdate(msg)).toBe(false);
    });

    it('returns false if backend_framerate is not an object', () => {
        const msg = {
            message_type: 'framerate_update',
            camera_group_id: 'group-0',
            backend_framerate: 30,
            frontend_framerate: {},
        };
        expect(isFramerateUpdate(msg)).toBe(false);
    });

    it('returns false if frontend_framerate is null', () => {
        const msg = {
            message_type: 'framerate_update',
            camera_group_id: 'group-0',
            backend_framerate: {},
            frontend_framerate: null,
        };
        expect(isFramerateUpdate(msg)).toBe(false);
    });
});
