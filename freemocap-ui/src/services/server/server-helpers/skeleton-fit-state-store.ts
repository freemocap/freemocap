// src/services/server/server-helpers/skeleton-fit-state-store.ts
import type {SkeletonFitStateSnapshot} from "./websocket-message-types";

export type SkeletonFitStates = Record<string, SkeletonFitStateSnapshot | null>;

const EMPTY_STATES: SkeletonFitStates = {};

/**
 * Latest per-pipeline segment-fit ritual states, pushed over the websocket.
 * Lives in a ref — no Redux, no re-renders of the provider tree. Consumers
 * subscribe via useSyncExternalStore; the server only sends on change, so
 * notifications arrive exactly when the ritual does something.
 */
export class SkeletonFitStateStore {
    private states: SkeletonFitStates = EMPTY_STATES;
    private readonly listeners = new Set<() => void>();

    update(states: SkeletonFitStates): void {
        this.states = states;
        this.listeners.forEach((listener) => listener());
    }

    getSnapshot = (): SkeletonFitStates => this.states;

    subscribe = (listener: () => void): (() => void) => {
        this.listeners.add(listener);
        return () => {
            this.listeners.delete(listener);
        };
    };

    clear(): void {
        this.update(EMPTY_STATES);
    }
}
