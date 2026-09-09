import type {ReactNode} from 'react';
import AnchoredInfo from '@/components/ui-components/AnchoredInfo';
import './settings-layout.css';

interface SettingRowProps {
    label: ReactNode;
    /** The explanation, opened from the info button beside the label.
     *
     *  Required, deliberately: a setting a user cannot interrogate is a setting
     *  they will guess at. Because the row carries no visible prose, this is the
     *  only place an explanation can live, so the compiler refuses a row without
     *  one rather than trusting anyone to remember. */
    info: {title: string; text: ReactNode};
    control: ReactNode;
    /** The single leading decision of a section — the one that reframes every
     *  row beneath it. At most one per section, or it means nothing. */
    promoted?: boolean;
    /** The governing switch is off. The row stays on screen and readable. */
    inactive?: boolean;
}

export default function SettingRow({label, info, control, promoted = false, inactive = false}: SettingRowProps) {
    const classes = ['setting-row'];
    if (promoted) classes.push('setting-row-promoted');
    if (inactive) classes.push('setting-row-inactive');
    return <div className={classes.join(' ')}>
        <span className="setting-row-label">
            {label}
            <AnchoredInfo title={info.title} text={info.text}/>
        </span>
        <div className="setting-row-control">{control}</div>
    </div>;
}
