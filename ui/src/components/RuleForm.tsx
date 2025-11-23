import { useEffect, useState } from "react";

export type ConditionType =
  | "extension"
  | "name_contains"
  | "size_gt_mb"
  | "size_lt_mb";

export type ActionType =
  | "move_to_folder"
  | "tag"
  | "delete"
  | "copy_to_bucket";

export interface RuleCondition {
  type: ConditionType;
  value: string;
}

export interface RuleAction {
  type: ActionType;
  value: string;
}

export interface RuleFormValues {
  name: string;
  description?: string;
  priority: number;
  enabled: boolean;
  conditions: RuleCondition[];
  actions: RuleAction[];
}

interface RuleFormProps {
  initial: RuleFormValues;
  onSubmit: (values: RuleFormValues) => void | Promise<void>;
}

const CONDITION_OPTIONS: { label: string; value: ConditionType }[] = [
  { label: "Extension equals", value: "extension" },
  { label: "Name contains", value: "name_contains" },
  { label: "Size > (MB)", value: "size_gt_mb" },
  { label: "Size < (MB)", value: "size_lt_mb" },
];

const ACTION_OPTIONS: { label: string; value: ActionType }[] = [
  { label: "Move to folder", value: "move_to_folder" },
  { label: "Add tag", value: "tag" },
  { label: "Delete", value: "delete" },
  { label: "Copy to bucket", value: "copy_to_bucket" },
];

export function RuleForm({ initial, onSubmit }: RuleFormProps) {
  const [values, setValues] = useState<RuleFormValues>(initial);

  // If "initial" changes (editing a rule), sync local state
  useEffect(() => {
    setValues(initial);
  }, [initial]);

  function update<K extends keyof RuleFormValues>(key: K, value: RuleFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function updateCondition(index: number, patch: Partial<RuleCondition>) {
    setValues((prev) => ({
      ...prev,
      conditions: prev.conditions.map((c, i) =>
        i === index ? { ...c, ...patch } : c
      ),
    }));
  }

  function addCondition() {
    setValues((prev) => ({
      ...prev,
      conditions: [
        ...prev.conditions,
        { type: "extension", value: "" } as RuleCondition,
      ],
    }));
  }

  function removeCondition(index: number) {
    setValues((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index),
    }));
  }

  function updateAction(index: number, patch: Partial<RuleAction>) {
    setValues((prev) => ({
      ...prev,
      actions: prev.actions.map((a, i) =>
        i === index ? { ...a, ...patch } : a
      ),
    }));
  }

  function addAction() {
    setValues((prev) => ({
      ...prev,
      actions: [
        ...prev.actions,
        { type: "move_to_folder", value: "" } as RuleAction,
      ],
    }));
  }

  function removeAction(index: number) {
    setValues((prev) => ({
      ...prev,
      actions: prev.actions.filter((_, i) => i !== index),
    }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(values);
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}
    >
      {/* Basic fields */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <label>Name</label>
        <input
          required
          value={values.name}
          onChange={(e) => update("name", e.target.value)}
          style={{
            borderRadius: 6,
            border: "1px solid #374151",
            padding: "4px 6px",
            background: "#020617",
            color: "inherit",
            fontSize: 12,
          }}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <label>Description</label>
        <textarea
          rows={2}
          value={values.description ?? ""}
          onChange={(e) => update("description", e.target.value)}
          style={{
            borderRadius: 6,
            border: "1px solid #374151",
            padding: "4px 6px",
            background: "#020617",
            color: "inherit",
            fontSize: 12,
          }}
        />
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label>Priority</label>
          <input
            type="number"
            value={values.priority}
            onChange={(e) => update("priority", Number(e.target.value))}
            style={{
              width: 70,
              borderRadius: 6,
              border: "1px solid #374151",
              padding: "4px 6px",
              background: "#020617",
              color: "inherit",
              fontSize: 12,
            }}
          />
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={values.enabled}
            onChange={(e) => update("enabled", e.target.checked)}
          />
          Enabled
        </label>
      </div>

      {/* Conditions */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <label>Conditions</label>
          <button
            type="button"
            onClick={addCondition}
            style={{
              fontSize: 11,
              borderRadius: 999,
              border: "1px solid #4b5563",
              background: "#111827",
              padding: "2px 8px",
              cursor: "pointer",
            }}
          >
            + Add
          </button>
        </div>

        {values.conditions.length === 0 && (
          <div style={{ fontSize: 11, color: "#6b7280" }}>
            No conditions — rule will match everything.
          </div>
        )}

        {values.conditions.map((c, idx) => (
          <div
            key={idx}
            style={{
              display: "flex",
              gap: 6,
              alignItems: "center",
              padding: 6,
              borderRadius: 6,
              border: "1px solid #1f2937",
              background: "#020617",
            }}
          >
            <select
              value={c.type}
              onChange={(e) =>
                updateCondition(idx, {
                  type: e.target.value as ConditionType,
                })
              }
              style={{
                fontSize: 12,
                borderRadius: 6,
                border: "1px solid #374151",
                padding: "4px 6px",
                background: "#020617",
                color: "inherit",
              }}
            >
              {CONDITION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <input
              value={c.value}
              onChange={(e) => updateCondition(idx, { value: e.target.value })}
              placeholder="Value"
              style={{
                flex: 1,
                fontSize: 12,
                borderRadius: 6,
                border: "1px solid #374151",
                padding: "4px 6px",
                background: "#020617",
                color: "inherit",
              }}
            />

            <button
              type="button"
              onClick={() => removeCondition(idx)}
              style={{
                fontSize: 11,
                borderRadius: 999,
                border: "none",
                background: "transparent",
                color: "#fca5a5",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <label>Actions</label>
          <button
            type="button"
            onClick={addAction}
            style={{
              fontSize: 11,
              borderRadius: 999,
              border: "1px solid #4b5563",
              background: "#111827",
              padding: "2px 8px",
              cursor: "pointer",
            }}
          >
            + Add
          </button>
        </div>

        {values.actions.length === 0 && (
          <div style={{ fontSize: 11, color: "#6b7280" }}>
            No actions — rule won&apos;t do anything.
          </div>
        )}

        {values.actions.map((a, idx) => (
          <div
            key={idx}
            style={{
              display: "flex",
              gap: 6,
              alignItems: "center",
              padding: 6,
              borderRadius: 6,
              border: "1px solid #1f2937",
              background: "#020617",
            }}
          >
            <select
              value={a.type}
              onChange={(e) =>
                updateAction(idx, {
                  type: e.target.value as ActionType,
                })
              }
              style={{
                fontSize: 12,
                borderRadius: 6,
                border: "1px solid #374151",
                padding: "4px 6px",
                background: "#020617",
                color: "inherit",
              }}
            >
              {ACTION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <input
              value={a.value}
              onChange={(e) => updateAction(idx, { value: e.target.value })}
              placeholder="Value"
              style={{
                flex: 1,
                fontSize: 12,
                borderRadius: 6,
                border: "1px solid #374151",
                padding: "4px 6px",
                background: "#020617",
                color: "inherit",
              }}
            />

            <button
              type="button"
              onClick={() => removeAction(idx)}
              style={{
                fontSize: 11,
                borderRadius: 999,
                border: "none",
                background: "transparent",
                color: "#fca5a5",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <button
        type="submit"
        style={{
          marginTop: 4,
          alignSelf: "flex-start",
          padding: "6px 10px",
          borderRadius: 6,
          border: "1px solid #4b5563",
          background: "#111827",
          fontSize: 12,
          cursor: "pointer",
        }}
      >
        Save rule
      </button>
    </form>
  );
}
