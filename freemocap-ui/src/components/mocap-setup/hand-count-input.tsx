import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import type {HandCount} from '@/store/slices/realtime/realtime-types';

export const HAND_COUNT_INFO = {
    title: 'Hand count',
    text: 'One and Two limit how many hands each camera tracks. Unknown lets the detector find additional hands.',
};

export function HandCountInput({value = 'two', onChange}: {value?: HandCount; onChange: (count: HandCount) => void}) {
    return <SettingSelectInput label="Hand count" value={value}
        options={[{label: 'One', value: 'one'}, {label: 'Two', value: 'two'}, {label: 'Unknown', value: 'unknown'}]}
        onChange={onChange}/>;
}
