import type { RootState } from '@/store/types';

export const selectIsServerConnected = (state: RootState) => state.connection.isConnected;
export const selectServerPid = (state: RootState) => state.connection.serverPid;
export const selectConnectionCameraGroups = (state: RootState) => state.connection.cameraGroups;
export const selectConnectionRealtimePipelines = (state: RootState) => state.connection.realtimePipelines;
