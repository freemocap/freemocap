import yaml from 'js-yaml';
import * as TOML from 'smol-toml';

export type SerializationFormat = 'json' | 'yaml' | 'toml';

/** Recursively remove null values from an object (TOML has no null concept). */
function stripNulls(obj: Record<string, unknown>): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
        if (value === null || value === undefined) continue;
        if (typeof value === 'object' && !Array.isArray(value)) {
            result[key] = stripNulls(value as Record<string, unknown>);
        } else {
            result[key] = value;
        }
    }
    return result;
}

export function serialize(data: Record<string, unknown>, format: SerializationFormat): string {
    switch (format) {
        case 'json':
            return JSON.stringify(data, null, 2);
        case 'yaml':
            return yaml.dump(data, {
                indent: 2,
                lineWidth: 120,
                noRefs: true,
                sortKeys: false,
            });
        case 'toml':
            // smol-toml expects a plain record; strip null values since TOML has no null
            return TOML.stringify(stripNulls(data) as any);
    }
}

export function deserialize(text: string, format: SerializationFormat): Record<string, unknown> {
    switch (format) {
        case 'json': {
            const parsed = JSON.parse(text);
            if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
                throw new Error('JSON root must be an object');
            }
            return parsed as Record<string, unknown>;
        }
        case 'yaml': {
            const parsed = yaml.load(text);
            if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
                throw new Error('YAML root must be a mapping');
            }
            return parsed as Record<string, unknown>;
        }
        case 'toml': {
            return TOML.parse(text) as Record<string, unknown>;
        }
    }
}

export function convertFormat(text: string, from: SerializationFormat, to: SerializationFormat): string {
    if (from === to) return text;
    const data = deserialize(text, from);
    return serialize(data, to);
}

export const FORMAT_EXTENSIONS: Record<SerializationFormat, string> = {
    json: '.json',
    yaml: '.yaml',
    toml: '.toml',
};

export const FORMAT_MIME_TYPES: Record<SerializationFormat, string> = {
    json: 'application/json',
    yaml: 'text/yaml',
    toml: 'application/toml',
};

export const FORMAT_MONACO_LANGUAGES: Record<SerializationFormat, string> = {
    json: 'json',
    yaml: 'yaml',
    toml: 'toml',
};
