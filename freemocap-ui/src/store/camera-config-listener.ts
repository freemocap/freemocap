import {createListenerMiddleware, ListenerEffectAPI} from '@reduxjs/toolkit';
import {cameraDesiredConfigUpdated, configCopiedToAll, recommendExposureForAll} from './slices/cameras/cameras-slice';
import {camerasConnectOrUpdate} from './slices/cameras/cameras-thunks';
import {RootState} from './root-state-types';

export const cameraConfigListenerMiddleware = createListenerMiddleware();

// Applies desired config to the backend when auto-apply is enabled.
// Debounced so rapid sequential changes coalesce into a single request.
function liveGroupForSelection(state: RootState) {
    return state.connection.cameraGroups.find(group => group.alive &&
        state.cameras.cameras.some(camera => camera.selected && camera.id in group.configs));
}

const autoApply = async (_: unknown, api: ListenerEffectAPI<any, any>) => {
    const state = api.getState() as RootState;
    const group = liveGroupForSelection(state);
    if (!state.cameras.autoApply || !group) return;

    // debounce: supersede any queued request so only the last value is sent
    api.cancelActiveListeners();
    await api.delay(350);
    const current = api.getState() as RootState;
    if (!current.cameras.autoApply || liveGroupForSelection(current)?.id !== group.id) return;

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
