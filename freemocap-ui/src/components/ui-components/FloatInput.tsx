import {useRef, useState} from 'react';
import './float-input.css';

interface FloatInputProps {
    label: string;
    value: string;
    sensitivity: number;
    onChange: (value: string) => void;
}

export default function FloatInput({label, value, sensitivity, onChange}: FloatInputProps) {
    const [editing, setEditing] = useState(false);
    const [text, setText] = useState(value);
    const original = useRef(value);
    const drag = useRef<{x: number; startX: number; value: number; moved: boolean} | null>(null);
    return <input className="float-input input-field text md br-1" aria-label={label}
        title="Drag to adjust · Shift for fine control · click or Enter to type · Escape to cancel"
        type="text" inputMode="decimal" value={editing ? text : value} readOnly={!editing}
        onChange={event => setText(event.target.value)}
        onBlur={() => {if (editing) onChange(text); setEditing(false);}}
        onPointerDown={event => {
            if (editing || event.button !== 0) return;
            original.current = value;
            const number = Number(value);
            if (!value.trim() || !Number.isFinite(number)) {setText(value); setEditing(true); return;}
            event.currentTarget.setPointerCapture(event.pointerId);
            drag.current = {x: event.clientX, startX: event.clientX, value: number, moved: false};
        }}
        onPointerMove={event => {
            const state = drag.current;
            if (!state) return;
            if (!state.moved && Math.abs(event.clientX - state.startX) < 3) return;
            state.moved = true;
            state.value += (event.clientX - state.x) * sensitivity * (event.shiftKey ? .1 : 1);
            state.x = event.clientX;
            if (Number.isFinite(state.value)) onChange(String(Number(state.value.toPrecision(12))));
        }}
        onPointerUp={event => {
            const state = drag.current;
            drag.current = null;
            if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
            if (state && !state.moved) {setText(value); setEditing(true); event.currentTarget.select();}
        }}
        onPointerCancel={() => {if (drag.current) onChange(original.current); drag.current = null;}}
        onKeyDown={event => {
            if (event.key === 'Escape') {
                event.stopPropagation(); if (drag.current) onChange(original.current); drag.current = null; setEditing(false);
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (editing) {onChange(text); setEditing(false);}
                else {original.current = value; setText(value); setEditing(true); event.currentTarget.select();}
            } else if (!editing && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
                event.preventDefault();
                const next = Number(value) + (event.key === 'ArrowRight' ? 1 : -1) * sensitivity * (event.shiftKey ? .1 : 1);
                if (value.trim() && Number.isFinite(next)) onChange(String(Number(next.toPrecision(12))));
            }
        }}/>;
}

