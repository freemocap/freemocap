// src/hooks/electron-service/electron-ipc-client.ts
import {createTRPCProxyClient} from '@trpc/client';
import superjson from 'superjson';
import type {AppAPI} from '../../../electron/main/api';

// Type for the electron API exposed via preload
interface ElectronAPI {
    invoke: (path: string, input?: any) => Promise<any>;
}

declare global {
    interface Window {
        electronAPI: ElectronAPI;
    }
}

// Observable-like class to satisfy tRPC requirements
class IPCObservable<T> {
    constructor(
        private subscribeFn: (observer: {
            next: (value: T) => void;
            error: (error: any) => void;
            complete: () => void;
        }) => { unsubscribe: () => void }
    ) {}

    subscribe(observer: {
        next: (value: T) => void;
        error: (error: any) => void;
        complete: () => void;
    }) {
        return this.subscribeFn(observer);
    }

    // Required pipe method for tRPC compatibility
    pipe(..._operations: any[]): any {
        // For IPC, we don't need complex piping, just return this
        return this;
    }
}

// Custom link for Electron IPC
const createElectronLink = () => {
    return () => {
        return ({ op }: any) => {
            return new IPCObservable((observer) => {
                const execute = async () => {
                    try {
                        // Check if electronAPI is available
                        if (!window.electronAPI) {
                            throw new Error('Electron API not available');
                        }

                        // Call through the IPC bridge
                        const serializedResult = await window.electronAPI.invoke(
                            op.path,
                            op.input
                        );

                        // Deserialize the result
                        const result = superjson.deserialize(serializedResult);

                        observer.next({
                            result: {
                                type: 'data',
                                data: result,
                            },
                        });
                        observer.complete();
                    } catch (error) {
                        console.error(`IPC Error for ${op.path}:`, error);
                        observer.error(
                            error instanceof Error
                                ? error
                                : new Error(String(error))
                        );
                    }
                };

                // Execute the request
                execute();

                // Return unsubscribe function
                return {
                    unsubscribe: () => {
                        // No-op for now, but could be used for cancellation
                    },
                };
            });
        };
    };
};

// Create the typed client - transformer moved to link if using newer tRPC
export const electronIpcClient = createTRPCProxyClient<AppAPI>({
    links: [createElectronLink()],
});

