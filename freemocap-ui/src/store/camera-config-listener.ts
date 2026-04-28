import {createListenerMiddleware, ListenerEffectAPI} from '@reduxjs/toolkit';
import {cameraDesiredConfigUpdated, configCopiedToAll, recommendExposureForAll} from './slices/cameras/cameras-slice';
import {camerasConnectOrUpdate} from './slices/cameras/cameras-thunks';

export const cameraConfigListenerMiddleware = createListenerMiddleware();

// Automatically applies desired config to the backend whenever a config mutation fires.
// Errors are silently swallowed — cameras may not be connected yet when changes come in.
const autoApply = async (_: unknown, api: ListenerEffectAPI<any, any>) => {
    try {
        await api.dispatch(camerasConnectOrUpdate()).unwrap();
    } catch {
        // no-op: backend may be unavailable or no cameras selected
    }
};

cameraConfigListenerMiddleware.startListening({
    actionCreator: cameraDesiredConfigUpdated,
    effect: autoApply,
});

cameraConfigListenerMiddleware.startListening({
    actionCreator: configCopiedToAll,
    effect: autoApply,
});

cameraConfigListenerMiddleware.startListening({
    actionCreator: recommendExposureForAll,
    effect: autoApply,
});
