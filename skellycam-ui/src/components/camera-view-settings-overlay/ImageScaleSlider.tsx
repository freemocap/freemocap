import React from 'react';

interface ImageScaleSliderProps {
    scale: number;
    onScaleChange: (value: number) => void;
}

export const ImageScaleSlider: React.FC<ImageScaleSliderProps> = ({ scale = 0.5, onScaleChange }) => {
    return (
        <div className="flex flex-col gap-1 p-1">
            <div className="flex justify-content-space-between items-center">
                <p className="text sm text-gray">Image Scale</p>
                <p className="text sm text-gray">{scale.toFixed(1)}x</p>
            </div>
            <input
                type="range"
                className="range-input"
                min={0.1}
                max={2.0}
                step={0.1}
                value={scale}
                onChange={(e) => onScaleChange(parseFloat(e.target.value))}
            />
            <div className="flex justify-content-space-between">
                <p className="text sm text-darkgray">0.1</p>
                <p className="text sm text-darkgray">0.5</p>
                <p className="text sm text-darkgray">2.0</p>
            </div>
        </div>
    );
};
