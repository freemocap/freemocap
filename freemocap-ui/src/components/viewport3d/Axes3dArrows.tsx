import React from 'react';

export const Axes3dArrows: React.FC = () => {
    const size = 1;

    return (
        <group>
            <axesHelper args={[size]} />
        </group>
    );
};
