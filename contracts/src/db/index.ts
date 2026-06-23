/**
 * Canonical DB schema — the typed contract.
 *
 * This is the source-of-truth DESCRIPTION of the canonical/platform tables. The
 * actual SQL lives in db/migrations (authored by the data-substrate agent); this
 * module is what the rest of the codebase imports and type-checks against, and
 * what the migrations must mirror.
 *
 * Security shape encoded here:
 *   - Only `pii_vault` columns are ever marked `pii: true`. INVARIANT 1: PII is
 *     vaulted and segregated; no behavioral table carries PII.
 *   - `canonical_uuid` everywhere outside the vault is an `opaqueRef` to the
 *     vault PK — opaque and random (INVARIANT 2), and crucially NOT a foreign
 *     key in the schema, so deleting the vault row severs identity while
 *     de-identified events remain and stay unlinkable.
 *   - `events` and `audit_log` are append-only/immutable (INVARIANT 5, 9).
 */

/** A column's logical type, mapped to Postgres in the migrations. */
export type ColumnType =
  | "uuid"
  | "text"
  | "timestamptz"
  | "date"
  | "jsonb"
  | "boolean"
  | "integer"
  | "numeric"
  | "enum";

export interface ColumnSpec {
  name: string;
  type: ColumnType;
  /** Allowed values when `type` is "enum". */
  enumValues?: readonly string[];
  nullable?: boolean;
  primaryKey?: boolean;
  /** True ONLY inside pii_vault. Encrypted + access-logged at rest. */
  pii?: boolean;
  /**
   * True when the column holds the opaque canonical identity ref. Deliberately
   * NOT a DB foreign key to the vault, so vault deletion severs identity without
   * cascading to behavioral rows.
   */
  opaqueRef?: boolean;
  /** Documented constraint(s) the migration enforces. */
  constraints?: readonly string[];
  description?: string;
}

export interface TableSpec {
  name: string;
  classification: "pii-vault" | "platform-canonical" | "audit";
  append_only: boolean;
  description: string;
  columns: readonly ColumnSpec[];
  /** Free-form table-level constraints / partitioning notes for the migration. */
  tableConstraints?: readonly string[];
}

const APP_VALUES = ["school", "learner", "platform"] as const;
const PURPOSE_VALUES = [
  "instruction",
  "assessment",
  "mastery",
  "intervention",
  "operations",
  "communication",
  "account",
] as const;
const ROLE_VALUES = ["admin", "teacher", "student", "parent"] as const;
const AGE_TIER_VALUES = ["child", "teen", "adult"] as const;

/**
 * pii_vault — the ONLY table that maps canonical_uuid to a person. Physically
 * separate, more-restricted store. Encrypted, access-logged.
 */
export const piiVault: TableSpec = {
  name: "pii_vault",
  classification: "pii-vault",
  append_only: false,
  description:
    "The only place canonical_uuid maps to a person. Segregated, restricted, encrypted, access-logged. Deleting a row severs identity (INVARIANT 1, 2).",
  columns: [
    { name: "canonical_uuid", type: "uuid", primaryKey: true, opaqueRef: true, description: "Random/opaque PK. Never derived from PII." },
    { name: "phone", type: "text", pii: true, nullable: true, description: "E.164. Encrypted at rest." },
    { name: "name", type: "text", pii: true, nullable: true, description: "Encrypted at rest." },
    { name: "dob", type: "date", pii: true, nullable: true, description: "Encrypted at rest." },
    { name: "email", type: "text", pii: true, nullable: true, description: "Encrypted at rest." },
    { name: "extra_pii", type: "jsonb", pii: true, nullable: true, description: "Any other PII, encrypted." },
    { name: "created_at", type: "timestamptz", description: "Row creation." },
    { name: "updated_at", type: "timestamptz", description: "Last PII update." },
  ],
  tableConstraints: ["Restricted role/grants separate from all other tables.", "Row-level access is logged to audit_log."],
};

/** app_memberships — User x App x Role x scope, time-bound. RBAC/ABAC inputs. */
export const appMemberships: TableSpec = {
  name: "app_memberships",
  classification: "platform-canonical",
  append_only: false,
  description: "Time-bound membership of an opaque identity in an app with a role and scope. Source of RBAC/ABAC inputs.",
  columns: [
    { name: "membership_id", type: "uuid", primaryKey: true },
    { name: "canonical_uuid", type: "uuid", opaqueRef: true, description: "Opaque identity ref. No FK to vault." },
    { name: "app", type: "enum", enumValues: APP_VALUES },
    { name: "role", type: "enum", enumValues: ROLE_VALUES },
    { name: "scope", type: "jsonb", description: "ABAC scope attributes (institution/grade/section)." },
    { name: "granted_at", type: "timestamptz" },
    { name: "revoked_at", type: "timestamptz", nullable: true, description: "Null while active." },
  ],
  tableConstraints: ["Unique active (canonical_uuid, app, role, scope) where revoked_at is null."],
};

/** consents — captured at the identity layer, referenced by every event. */
export const consents: TableSpec = {
  name: "consents",
  classification: "platform-canonical",
  append_only: false,
  description: "Consent grants. Referenced by consent_ref on every event; gates every cross-context read (INVARIANT 6).",
  columns: [
    { name: "consent_id", type: "uuid", primaryKey: true, description: "Referenced as consent_ref on events." },
    { name: "canonical_uuid", type: "uuid", opaqueRef: true },
    { name: "scope", type: "text", description: "Data scope this consent covers." },
    { name: "purpose", type: "enum", enumValues: PURPOSE_VALUES },
    { name: "age_tier", type: "enum", enumValues: AGE_TIER_VALUES },
    { name: "granted_by", type: "uuid", opaqueRef: true, description: "Self, or guardian for child/teen." },
    { name: "granted_at", type: "timestamptz" },
    { name: "revoked_at", type: "timestamptz", nullable: true },
  ],
};

/** events — append-only, immutable, partitioned. The behavioral store. NO PII. */
export const events: TableSpec = {
  name: "events",
  classification: "platform-canonical",
  append_only: true,
  description: "Append-only, immutable, partitioned behavioral event store. Keyed by opaque canonical_uuid; never carries PII (INVARIANT 1, 5).",
  columns: [
    { name: "event_id", type: "uuid", primaryKey: true },
    { name: "canonical_uuid", type: "uuid", opaqueRef: true, description: "Opaque subject ref. No FK to vault — deletion leaves events unlinkable." },
    { name: "app", type: "enum", enumValues: APP_VALUES },
    { name: "type", type: "text", description: "Event type (matches the event contract union)." },
    { name: "purpose", type: "enum", enumValues: PURPOSE_VALUES },
    { name: "consent_ref", type: "uuid", description: "References consents.consent_id (INVARIANT 6)." },
    { name: "payload", type: "jsonb", description: "Typed per `type` per the event contract. No PII." },
    { name: "schema_version", type: "text", constraints: ["default 'v1'"] },
    { name: "occurred_at", type: "timestamptz", description: "Source-of-truth time." },
    { name: "recorded_at", type: "timestamptz", description: "Store-accepted time." },
  ],
  tableConstraints: [
    "INSERT-only: no UPDATE or DELETE grants (immutable, append-only).",
    "Partitioned by recorded_at (range).",
    "CHECK: payload contains no top-level PII keys (defense-in-depth).",
  ],
};

/** audit_log — immutable record of privileged/governed actions (INVARIANT 9). */
export const auditLog: TableSpec = {
  name: "audit_log",
  classification: "audit",
  append_only: true,
  description: "Immutable audit of every gateway call and privileged/break-glass action (INVARIANT 9). No PII.",
  columns: [
    { name: "audit_id", type: "uuid", primaryKey: true },
    { name: "actor_canonical_uuid", type: "uuid", opaqueRef: true, nullable: true, description: "Opaque ref to the actor; null for system." },
    { name: "app", type: "enum", enumValues: APP_VALUES, nullable: true },
    { name: "action", type: "text", description: "capability.operation invoked." },
    { name: "decision", type: "enum", enumValues: ["allow", "deny"] as const },
    { name: "resource_scope", type: "jsonb", nullable: true, description: "ABAC attributes evaluated." },
    { name: "reasons", type: "jsonb", nullable: true, description: "Policy reasons, for explainability." },
    { name: "break_glass", type: "boolean", constraints: ["default false"], description: "True for privileged override actions." },
    { name: "request_id", type: "uuid", nullable: true },
    { name: "recorded_at", type: "timestamptz" },
  ],
  tableConstraints: ["INSERT-only: no UPDATE or DELETE grants."],
};

/** The full canonical schema, in dependency order. Migrations mirror this. */
export const canonicalSchema: readonly TableSpec[] = [piiVault, appMemberships, consents, events, auditLog];

/** Lookup by table name. */
export const canonicalTables: Record<string, TableSpec> = {
  pii_vault: piiVault,
  app_memberships: appMemberships,
  consents,
  events,
  audit_log: auditLog,
};
