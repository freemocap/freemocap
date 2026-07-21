import React from 'react';

export const Row: React.FC<{label: string; indent?: boolean; children: React.ReactNode}> = ({label, indent, children}) => (
    <div className="text-input-container gap-1 p-1 br-1 flex justify-content-space-between items-center">
        <p className="text md text-gray text-nowrap flex items-center gap-1" style={{minWidth: 80}}>
            {indent && <span className="icon icon-size-20 subcat-icon" />}
            {label}
        </p>
        <div className="flex-1 flex flex-end">
            {children}
        </div>
    </div>
);
