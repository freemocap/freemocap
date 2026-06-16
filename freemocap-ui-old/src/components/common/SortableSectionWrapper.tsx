import React, {ReactNode} from "react";
import {useSortable} from "@dnd-kit/sortable";
import {CSS} from "@dnd-kit/utilities";
import {DragHandleContext} from "@/components/common/DragHandleContext";

interface SortableSectionWrapperProps {
    id: string;
    children: ReactNode;
}

export const SortableSectionWrapper: React.FC<SortableSectionWrapperProps> = ({
    id,
    children,
}) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({id});

    const style: React.CSSProperties = {
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 10 : undefined,
        position: "relative",
        opacity: isDragging ? 0.85 : 1,
    };

    return (
        <div ref={setNodeRef} style={style}>
            <DragHandleContext.Provider value={{listeners, attributes}}>
                {children}
            </DragHandleContext.Provider>
        </div>
    );
};
