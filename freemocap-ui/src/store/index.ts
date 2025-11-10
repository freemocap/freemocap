export { store } from './store';
export type { RootState, AppDispatch, AppThunk } from './types';
export { useAppDispatch, useAppSelector } from './hooks';


// Re-export all slice actions and selectors for a nice 'barrel' design pattern, which makes imports cleaner
export * from './slices/cameras';
export * from './slices/recording';
export * from './slices/framerate';
export * from './slices/log-records';
export * from './slices/theme';
export * from './slices/videos';
export * from './slices/pipeline';
export * from './slices/mocap';
