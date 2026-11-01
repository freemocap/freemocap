import DropdownButton from '../ui-components/DropdownButton';
import ButtonSm from '../ui-components/ButtonSm';

export default function ProcessingPipelineSelect() {
    return <div role="group" aria-label="Processing pipeline">
        <DropdownButton buttonProps={{text: 'Typed data flow graph V1', rightSideIcon: 'dropdown'}}
            dropdownItems={<div role="listbox" aria-label="Processing pipeline options">
                <div role="option" aria-selected="true">Typed data flow graph V1</div>
                <div role="option" aria-disabled="true" aria-selected="false">
                    <ButtonSm text="Add custom pipeline…" disabled tooltip tooltipText="Coming soon" />
                </div>
            </div>} />
    </div>;
}
