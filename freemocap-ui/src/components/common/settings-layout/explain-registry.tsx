// Settings rows inside an explain scope register their element and info text, so an explain view can point
// at every setting with the same text as its info button. Outside a scope, registration does nothing.
import {createContext, type ReactNode, useCallback, useContext, useRef} from 'react';

export interface ExplainEntry {
    key: string;
    title: string;
    text: ReactNode;
    element: HTMLElement;
    /** Which edge of the node the thing explained sits nearest. */
    side: 'left' | 'right';
}

interface ExplainRegistry {
    set: (key: string, entry: Omit<ExplainEntry, 'key'> | null) => void;
}

const ExplainContext = createContext<ExplainRegistry | null>(null);

/** Collects the entries registered by everything rendered inside it. */
export function useExplainScope(): {entries: () => ExplainEntry[]; Scope: (props: {children: ReactNode}) => ReactNode} {
    const map = useRef(new Map<string, Omit<ExplainEntry, 'key'>>());
    const registry = useRef<ExplainRegistry>({set: (key, entry) => {
        if (entry) map.current.set(key, entry);
        else map.current.delete(key);
    }});
    const entries = useCallback(() => [...map.current.entries()].map(([key, entry]) => ({key, ...entry})), []);
    const Scope = useCallback(({children}: {children: ReactNode}) =>
        <ExplainContext.Provider value={registry.current}>{children}</ExplainContext.Provider>, []);
    return {entries, Scope};
}

/** A ref callback that registers its element with the enclosing explain scope, if there is one. */
export function useExplainTarget(key: string, title: string, text: ReactNode, side: 'left' | 'right'): (element: HTMLElement | null) => void {
    const registry = useContext(ExplainContext);
    return useCallback((element: HTMLElement | null) => {
        if (!registry) return;
        registry.set(key, element ? {title, text, element, side} : null);
    }, [registry, key, title, text, side]);
}
