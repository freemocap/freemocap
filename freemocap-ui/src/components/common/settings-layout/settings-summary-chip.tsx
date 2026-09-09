import type {ReactNode} from 'react';
import './settings-layout.css';

type SummaryChipTone = 'neutral' | 'quiet' | 'positive' | 'path';

const toneClass: Record<SummaryChipTone, string> = {
    neutral: '',
    quiet: 'settings-summary-chip-quiet',
    positive: 'settings-summary-chip-positive',
    path: 'settings-summary-chip-path',
};

/**
 * A fact about the section's current state, shown in its header.
 *
 * It states only what IS. Pass nothing when a feature is switched off and the
 * chip removes itself, rather than rendering "none" or "no board".
 */
export default function SettingsSummaryChip({tone = 'neutral', title, children}:
    {tone?: SummaryChipTone; title?: string; children?: ReactNode}) {
    return <span className={`settings-summary-chip ${toneClass[tone]}`.trim()} title={title}>{children}</span>;
}
