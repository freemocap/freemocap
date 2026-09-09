import type {ReactNode} from 'react';
import './settings-layout.css';

/**
 * Rows governed by the control immediately above them. The rail carries the
 * dependency; the rows themselves stay visible and readable whether or not
 * the governing control is on.
 */
export default function DependentRowGroup({children}: {children: ReactNode}) {
    return <div className="settings-dependent-group">{children}</div>;
}
