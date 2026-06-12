import React, {useEffect, useRef, useState} from "react";
import IconButton from "@/components/ui-components/IconButton";

/** Rounds to the precision of `step` and clamps to [min, max], avoiding float drift like 0.005 - 0.0005 = 0.0045000000000000005. */
function roundToStep(value: number, step: number, min: number, max: number): number {
    const decimals = (step.toString().split(".")[1] || "").length;
    const rounded = Number(value.toFixed(decimals));
    return Math.max(min, Math.min(max, rounded));
}

interface InputWithUnitProps {
    value: number;
    onChange: (value: number) => void;
    unit?: string;
    min?: number;
    max?: number;
    step?: number;
    onEnter?: () => void;
}

const InputWithUnit: React.FC<InputWithUnitProps> = ({value, onChange, unit = "", min = 1, max = 999, step = 1, onEnter}) => {
    const inputRef = useRef<HTMLInputElement>(null);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            onEnter?.();
            inputRef.current?.blur();
        }
    };

    return (
        <div className="input-with-unit tooltip">
            <input
                ref={inputRef}
                type="number"
                value={value}
                min={min}
                max={max}
                step={step}
                onChange={e => onChange(Math.max(min, Math.min(max, Number(e.target.value) || min)))}
                onFocus={e => e.target.select()}
                onKeyDown={handleKeyDown}
                className="input-field text md text-center"
            />
            {unit && <span className="unit-label text md">{unit}</span>}
        </div>
    );
};

interface ValueSelectorProps {
    value?: number;
    unit?: string;
    min?: number;
    max?: number;
    step?: number;
    onChange?: (value: number) => void;
}

const ValueSelector: React.FC<ValueSelectorProps> = ({value, unit = "", min = 1, max = 999, step = 1, onChange}) => {
    const [open, setOpen] = useState(false);
    const [popupStyle, setPopupStyle] = useState<React.CSSProperties>({});
    const containerRef = useRef<HTMLDivElement>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);

    const currentValue = value ?? min;

    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const handleOpen = () => {
        if (!open && buttonRef.current) {
            const rect = buttonRef.current.getBoundingClientRect();
            const spaceBelow = window.innerHeight - rect.bottom;
            const style: React.CSSProperties = {
               
            };
            if (spaceBelow < 68) {
                style.bottom = window.innerHeight - rect.top + 4;
            } else {
                style.top = rect.bottom + 4;
            }
            setPopupStyle(style);
        }
        setOpen(prev => !prev);
    };

    return (
        <div ref={containerRef} className="value-selector pos-rel inline-block">
            <button ref={buttonRef} className="input-with-unit button sm fit-content dropdown" onClick={handleOpen}>
                <span className="value-label text md">{currentValue}</span>
                {unit && <span className="unit-label text md">{unit}</span>}
            </button>

            {open && (
                <div className="value-selector-container pos-abs border-1 border-black elevated-sharp flex flex-row p-1 bg-dark br-2 z-1 reveal slide-down">
                    <div className="flex right-0 p-2 gap-2 bg-middark br-1 z-1">
                        <IconButton
                            icon="minus-icon"
                            onClick={() => currentValue > min && onChange?.(roundToStep(currentValue - step, step, min, max))}
                            disabled={currentValue <= min}
                            className={`icon-size-25 ${currentValue <= min ? "deactivated" : ""}`}
                            iconSize="icon-size-20"
                        />
                        <InputWithUnit
                            value={currentValue}
                            onChange={onChange ?? (() => {})}
                            unit={unit}
                            min={min}
                            max={max}
                            step={step}
                            onEnter={() => setOpen(false)}
                        />
                        <IconButton
                            icon="plus-icon"
                            onClick={() => currentValue < max && onChange?.(roundToStep(currentValue + step, step, min, max))}
                            disabled={currentValue >= max}
                            className={`icon-size-25 ${currentValue >= max ? "deactivated" : ""}`}
                            iconSize="icon-size-20"
                        />
                    </div>
                </div>
            )}
        </div>
    );
};

export default ValueSelector;
