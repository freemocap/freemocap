import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';

const OPTIONS = [
    {value: 'pelvis', label: 'Pelvis'},
    {value: 'skull', label: 'Head (skull)'},
    {value: 'thoracic', label: 'Chest'},
    {value: 'left_carpals', label: 'Left wrist'},
    {value: 'right_carpals', label: 'Right wrist'},
];

const INFO = {
    title: 'Skeleton anchor',
    text: <p>Choose the tracked body segment that positions the connected skeleton.
        Changing the anchor preserves fitted lengths and anatomical joint definitions.
        The selected segment must be visible.</p>,
};

export default function SkeletonAnchorSetting({value, onChange}: {
    value: string;
    onChange: (value: string) => void;
}) {
    return <SettingRow label="Skeleton anchor" info={INFO}
        control={<SettingSelectInput label="Skeleton anchor" value={value}
            options={OPTIONS} onChange={onChange}/>}/>;
}
