import { useEffect, useState } from "react";
import {
  RuleForm,
  type RuleFormValues,
  type RuleAction,
  type RuleCondition,
} from "../components/RuleForm";

export interface Rule extends RuleFormValues {
  id: string;
}

interface RulesPageProps {
  apiBase: string;
}

export function RulesPage({ apiBase }: RulesPageProps) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadRules() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/rules`);
      if (!res.ok) throw new Error(`Failed to load rules (${res.status})`);
      const data = (await res.json()) as Rule[];
      setRules(data);
    } catch (err: any) {
      setError(err.message || "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRules();
  }, [apiBase]);

  async function handleCreate(values: RuleFormValues) {
    setError(null);
    const res = await fetch(`${apiBase}/rules`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Create failed (${res.status})`);
    }
    await loadRules();
  }

  async function handleUpdate(id: string, values: RuleFormValues) {
    setError(null);
    const res = await fetch(`${apiBase}/rules/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Update failed (${res.status})`);
    }
    setEditingRule(null);
    await loadRules();
  }

  async function handleDelete(id: string) {
    setError(null);
    if (!window.confirm("Delete this rule?")) return;
    const res = await fetch(`${apiBase}/rules/${id}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Delete failed (${res.status})`);
    }
    await loadRules();
  }

  async function handleReorder(newOrderIds: string[]) {
    setError(null);
    const res = await fetch(`${apiBase}/rules/reorder`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newOrderIds),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Reorder failed (${res.status})`);
    }
    await loadRules();
  }

  function moveRule(index: number, direction: "up" | "down") {
    const newRules = [...rules];
    if (direction === "up" && index > 0) {
      [newRules[index - 1], newRules[index]] = [
        newRules[index],
        newRules[index - 1],
      ];
    } else if (direction === "down" && index < newRules.length - 1) {
      [newRules[index + 1], newRules[index]] = [
        newRules[index],
        newRules[index + 1],
      ];
    } else {
      return;
    }

    const ids = newRules.map((r) => r.id);
    handleReorder(ids).catch((err: any) => {
      setError(err.message || "Reorder failed");
    });
  }

  const defaultConditions: RuleCondition[] = [];
  const defaultActions: RuleAction[] = [];

  return (
    <div
      style={{
        border: "1px solid #1f2937",
        borderRadius: 10,
        padding: 16,
        background: "#020617",
      }}
    >
      <div
        style={{
          marginBottom: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
        }}
      >
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Rules</h2>
          <p style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>
            Rules are evaluated in order (top to bottom). Lower priority number
            means earlier evaluation.
          </p>
        </div>
        {loading && (
          <span style={{ fontSize: 11, color: "#6b7280" }}>Loading...</span>
        )}
      </div>

      {error && (
        <div
          style={{
            marginBottom: 10,
            fontSize: 12,
            color: "#fecaca",
            borderRadius: 6,
            padding: "6px 8px",
            background: "#7f1d1d",
          }}
        >
          {error}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1fr)",
          gap: 16,
        }}
      >
        {/* Create rule */}
        <div
          style={{
            border: "1px solid #1f2937",
            borderRadius: 8,
            padding: 10,
            background: "#050a1a",
          }}
        >
          <h3 style={{ fontSize: 14, fontWeight: 500, marginBottom: 6 }}>
            Create rule
          </h3>
          <RuleForm
            initial={{
              name: "",
              description: "",
              enabled: true,
              priority: rules.length,
              conditions: defaultConditions,
              actions: defaultActions,
            }}
            onSubmit={async (vals) => {
              try {
                await handleCreate(vals);
              } catch (err: any) {
                setError(err.message || "Create failed");
              }
            }}
          />
        </div>

        {/* Existing rules */}
        <div
          style={{
            border: "1px solid #1f2937",
            borderRadius: 8,
            padding: 10,
            background: "#050a1a",
          }}
        >
          <h3 style={{ fontSize: 14, fontWeight: 500, marginBottom: 6 }}>
            Existing rules
          </h3>
          <div
            style={{
              maxHeight: 350,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              fontSize: 12,
            }}
          >
            {rules.map((r, idx) => (
              <div
                key={r.id}
                style={{
                  border: "1px solid #1f2937",
                  borderRadius: 6,
                  padding: 8,
                  background: "#020617",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 4,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 500, fontSize: 13 }}>
                      #{r.priority} • {r.name}
                    </div>
                    {r.description && (
                      <div style={{ fontSize: 11, color: "#9ca3af" }}>
                        {r.description}
                      </div>
                    )}
                  </div>
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      fontSize: 11,
                      alignItems: "center",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => moveRule(idx, "up")}
                      disabled={idx === 0}
                      style={{
                        borderRadius: 999,
                        border: "1px solid #374151",
                        background: "#020617",
                        color: idx === 0 ? "#4b5563" : "#e5e7eb",
                        padding: "2px 6px",
                        cursor: idx === 0 ? "default" : "pointer",
                      }}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={() => moveRule(idx, "down")}
                      disabled={idx === rules.length - 1}
                      style={{
                        borderRadius: 999,
                        border: "1px solid #374151",
                        background: "#020617",
                        color:
                          idx === rules.length - 1 ? "#4b5563" : "#e5e7eb",
                        padding: "2px 6px",
                        cursor:
                          idx === rules.length - 1 ? "default" : "pointer",
                      }}
                    >
                      ↓
                    </button>
                    <button
                      style={{
                        background: "transparent",
                        color: "#93c5fd",
                        border: "none",
                        cursor: "pointer",
                      }}
                      onClick={() => setEditingRule(r)}
                    >
                      Edit
                    </button>
                    <button
                      style={{
                        background: "transparent",
                        color: "#fca5a5",
                        border: "none",
                        cursor: "pointer",
                      }}
                      onClick={() => {
                        handleDelete(r.id).catch((err: any) =>
                          setError(err.message || "Delete failed")
                        );
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div style={{ fontSize: 11, color: "#9ca3af" }}>
                  {r.enabled ? "Enabled" : "Disabled"} •{" "}
                  {r.conditions.length} conditions • {r.actions.length} actions
                </div>
              </div>
            ))}

            {!rules.length && !loading && (
              <div style={{ fontSize: 12, color: "#6b7280" }}>
                No rules yet. Create one on the left.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Edit modal */}
      {editingRule && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 50,
          }}
        >
          <div
            style={{
              background: "#020617",
              border: "1px solid #374151",
              borderRadius: 10,
              padding: 16,
              width: "100%",
              maxWidth: 520,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 8,
              }}
            >
              <h3 style={{ fontSize: 14, fontWeight: 500 }}>Edit rule</h3>
              <button
                onClick={() => setEditingRule(null)}
                style={{
                  border: "none",
                  background: "transparent",
                  color: "#9ca3af",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                Close
              </button>
            </div>

            <RuleForm
              initial={editingRule}
              onSubmit={async (vals) => {
                try {
                  await handleUpdate(editingRule.id, vals);
                } catch (err: any) {
                  setError(err.message || "Update failed");
                }
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
