// transport/application-kinds.ts
//
// Message kinds defined by an application that reuses this stream for its own
// server, for example a robot publishing its motor state beside FreeMoCap frames.
// They keep the protocol's guarantees: the same envelope (kind, version, timestamp,
// sequence), and every message validates on its own with no handshake or held
// state. FreeMoCap's kinds cannot be redefined, and a kind that nobody registered
// is still skipped (fail soft), exactly as before.

import { z } from "zod";
import { ENVELOPE, KNOWN_KINDS } from "./message-contract.js";

/** Validates messages of one application-defined kind. A Zod schema qualifies. */
export interface ApplicationKind<T = unknown> {
    /** Message-shape version this client reads (default 0). Messages declaring
     *  another version are skipped like an unknown kind. */
    readonly version?: number;
    /** Return the validated application value; the envelope is validated separately.
     *  Throw when a message at the supported version is malformed. */
    parse(message: unknown): T;
}

/** Application-defined kinds keyed by the wire's `kind` value. */
export type ApplicationKinds = Readonly<Record<string, ApplicationKind>>;

/** The validated message delivered for one application kind. */
export type ApplicationMessage<Kind extends ApplicationKind> = ReturnType<Kind["parse"]>;

const ApplicationEnvelopeSchema = z.object({ kind: z.string(), ...ENVELOPE });

/** Reject a registry that would redefine a FreeMoCap kind. */
export function validateApplicationKinds(kinds: ApplicationKinds): void {
    for (const kind of Object.keys(kinds)) {
        if (!kind.trim() || typeof kinds[kind]?.parse !== 'function') {
            throw new Error('Application kinds need a nonempty name and a parser');
        }
        const version = kinds[kind].version ?? 0;
        if (!Number.isSafeInteger(version) || version < 0) {
            throw new Error(`Invalid version for application kind "${kind}"`);
        }
        if ((KNOWN_KINDS as readonly string[]).includes(kind)) {
            throw new Error(`"${kind}" is a FreeMoCap message kind and cannot be redefined`);
        }
    }
}

/** Validate one decoded message of a registered application kind.
 *  Returns null for a version the kind does not read (fail soft, like FreeMoCap's
 *  kinds). Throws for a malformed envelope or payload (fail loud — a defect). */
export function parseApplicationMessage<T>(kind: ApplicationKind<T>, raw: unknown): T | null {
    if (raw === null || typeof raw !== "object") return null;
    if ((raw as { version?: unknown }).version !== (kind.version ?? 0)) return null;
    ApplicationEnvelopeSchema.parse(raw);
    return kind.parse(raw);
}
