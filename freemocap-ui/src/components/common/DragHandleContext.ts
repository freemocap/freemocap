import {createContext, useContext} from "react";

export interface DragHandleContextValue {
    listeners: Record<string, Function> | undefined;
    attributes: Record<string, any>;
}

export const DragHandleContext = createContext<DragHandleContextValue | null>(null);

export const useDragHandle = (): DragHandleContextValue | null => {
    return useContext(DragHandleContext);
};
