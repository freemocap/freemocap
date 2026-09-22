import type {Matrix4} from 'three';
import {transformFields, TransformRepresentation} from './reference-transform';

export default function ReferenceTransformSummary({
    matrix, label = 'Defined transformation',
}: {matrix: Matrix4; label?: string}) {
    const fields = transformFields(matrix, TransformRepresentation.Quaternion);
    const preview = (values: number[]) =>
        values.map(value => Number(value.toFixed(3))).join(', ');
    return <output className="reference-transform-summary" aria-label={label}>
        <span><span className="reference-transform-term">q (wxyz)</span>[{preview(fields.slice(3))}]</span>
        <span><span className="reference-transform-term">t (xyz) mm</span>[{preview(fields.slice(0, 3))}]</span>
    </output>;
}
