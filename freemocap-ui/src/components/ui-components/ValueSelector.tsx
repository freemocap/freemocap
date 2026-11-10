import React, {useEffect, useRef, useState} from "react";
import IconButton from "@/components/ui-components/IconButton";

/**
 * Rounds to the precision of `step` and clamps to [min, max],
 * avoiding float drift like:
 * 0.005 - 0.0005 = 0.0045000000000000005
 */
function roundToStep(
    value: number,
    step: number,
    min: number,
    max: number
): number {
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
    disabled?: boolean;
    ariaLabel?: string;
    empty?: boolean;
}

const InputWithUnit: React.FC<InputWithUnitProps> = ({
    value,
    onChange,
    unit = "",
    min = 1,
    max = 999,
    step = 1,
    disabled = false,
    ariaLabel,
    empty = false,
}) => {
    const inputRef = useRef<HTMLInputElement>(null);
    const cancelOnBlur = useRef(false);

    /*
     * The text that stands for the external value. An empty field has no
     * value to show, so its text is blank and the placeholder shows instead.
     */
    const valueText = empty ? "" : String(value);

    /*
     * Keep the user's current text separate from the numeric Redux value.
     *
     * This allows temporary editing states such as:
     * "", "0", "0.", and "0.01"
     */
    const [inputText, setInputText] = useState(valueText);
    const [isEditing, setIsEditing] = useState(false);

    /*
     * Synchronize with external value changes, such as the plus/minus buttons,
     * as long as the user is not currently typing in the field.
     */
    useEffect(() => {
        if (!isEditing) {
            setInputText(valueText);
        }
    }, [valueText, isEditing]);

    const commitValue = () => {
        // blur fires synchronously before Escape's state updates render.
        if (cancelOnBlur.current) {
            cancelOnBlur.current = false;
            setInputText(valueText);
            setIsEditing(false);
            return;
        }
        const trimmedInput = inputText.trim();
        const parsedValue = Number(trimmedInput);

        /*
         * An empty or invalid value should restore the last valid external
         * value instead of being converted immediately to `min`.
         */
        if (
            trimmedInput === "" ||
            !Number.isFinite(parsedValue)
        ) {
            setInputText(valueText);
            setIsEditing(false);
            return;
        }

        const nextValue = roundToStep(
            parsedValue,
            step,
            min,
            max
        );

        onChange(nextValue);
        setInputText(String(nextValue));
        setIsEditing(false);
    };

    const handleFocus = (
        event: React.FocusEvent<HTMLInputElement>
    ) => {
        setIsEditing(true);

        /*
         * Select the current value when entering the field so that typing
         * immediately replaces it.
         */
        event.currentTarget.select();
    };

    const handleKeyDown = (
        event: React.KeyboardEvent<HTMLInputElement>
    ) => {
        if (event.key === "Enter") {
            inputRef.current?.blur();
            return;
        }

        if (event.key === "Escape") {
            cancelOnBlur.current = true;
            setInputText(valueText);
            setIsEditing(false);
            inputRef.current?.blur();
        }
    };

    return (
        <div className="input-with-unit tooltip">
            <input
                ref={inputRef}
                type="number"
                aria-label={ariaLabel}
                placeholder={empty ? "â€”" : undefined}
                value={inputText}
                min={min}
                max={max}
                step={step}
                disabled={disabled}
                onChange={(event) =>
                    setInputText(event.target.value)
                }
                onFocus={handleFocus}
                onBlur={commitValue}
                onKeyDown={handleKeyDown}
                className="input-field text md w-full text-center"
            />

            {unit && (
                <span className="unit-label text md">
                    {unit}
                </span>
            )}
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
    disabled?: boolean;
    /** Names the number field; the steppers become "Decrease â€¦" and "Increase â€¦". */
    ariaLabel?: string;
    /**
     * There is no value to show yet: the field is blank with a "â€”" placeholder
     * and the steppers are off. Typing still sets a value; add `disabled` to
     * lock the field as well.
     */
    empty?: boolean;
}

const ValueSelector: React.FC<ValueSelectorProps> = ({
    value,
    unit = "",
    min = 1,
    max = 999,
    step = 1,
    onChange,
    disabled = false,
    ariaLabel,
    empty = false,
}) => {
    const currentValue = value ?? min;
    /* An empty field has no value to step from. */
    const steppersDisabled = disabled || empty;

    return (
        <div
            className={
                `value-selector-container flex flex-row items-center ` +
                `gap-2 bg-middark br-1 ${disabled ? "disabled" : ""}`
            }
        >
            <IconButton
                icon="minus-icon"
                onClick={() => {
                    if (currentValue > min) {
                        onChange?.(
                            roundToStep(
                                currentValue - step,
                                step,
                                min,
                                max
                            )
                        );
                    }
                }}
                disabled={steppersDisabled || currentValue <= min}
                ariaLabel={ariaLabel && `Decrease ${ariaLabel}`}
                className={
                    `icon-size-25 ${
                        steppersDisabled || currentValue <= min
                            ? "deactivated"
                            : ""
                    }`
                }
                iconSize="icon-size-20"
            />

            <InputWithUnit
                value={currentValue}
                onChange={onChange ?? (() => {})}
                unit={unit}
                min={min}
                max={max}
                step={step}
                disabled={disabled}
                ariaLabel={ariaLabel}
                empty={empty}
            />

            <IconButton
                icon="plus-icon"
                onClick={() => {
                    if (currentValue < max) {
                        onChange?.(
                            roundToStep(
                                currentValue + step,
                                step,
                                min,
                                max
                            )
                        );
                    }
                }}
                disabled={steppersDisabled || currentValue >= max}
                ariaLabel={ariaLabel && `Increase ${ariaLabel}`}
                className={
                    `icon-size-25 ${
                        steppersDisabled || currentValue >= max
                            ? "deactivated"
                            : ""
                    }`
                }
                iconSize="icon-size-20"
            />
        </div>
    );
};

export default ValueSelector;
