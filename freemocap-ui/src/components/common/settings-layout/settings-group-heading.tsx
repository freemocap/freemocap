import type {ReactNode} from 'react';
import AnchoredInfo from '@/components/ui-components/AnchoredInfo';
import './settings-layout.css';

interface SettingsGroupHeadingProps {
    text: string;
    /** Required for the same reason as on SettingRow: a group that names a
     *  concept has to be able to explain that concept. */
    info: {title: string; text: ReactNode};
}

export default function SettingsGroupHeading({text, info}: SettingsGroupHeadingProps) {
    return <h3 className="settings-group-heading">
        {text}
        <AnchoredInfo title={info.title} text={info.text}/>
    </h3>;
}
