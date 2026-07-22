import type {Tour} from '../types';
import {gettingStartedTour} from './getting-started';

// Registry of all tours. A new tour is one import + one entry here.
export const TOURS: Record<string, Tour> = {
    'getting-started': gettingStartedTour,
};

export type TourId = keyof typeof TOURS;
