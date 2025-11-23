import { useEffect, useState } from "react";

export interface ActivityEvent {
  id: string;
  timestamp: string; // ISO string from backend
  bucket: string;
  object: string;
  status: "pending" | "processed" | "error";
  rule_name?: string | null;
  actions: string[];
  error_message?: string | null;
}

interface ActivityPanelProps {
  apiBase: string;
}

export function ActivityPanel({ apiBase }: ActivityPanelProps) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadActivity() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/activity?limit=20`);
      if (!res.ok) throw new Error(`Failed to load activity (${res.status})`);
      const data = (await res.json()) as ActivityEvent[];
      setEvents(data);
    } catch (err: any) {
      setError(err.message || "Failed to load activity");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadActivity();
  }, [apiBase]);

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
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>Recent activity</h2>
          <p style={{ fontSize: 12, color: "#9ca3af", marginTop: 2 }}>
            Latest files processed by the orchestrator.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {loading && (
            <span style={{ fontSize: 11, color: "#6b7280" }}>Loading...</span>
          )}
          <button
            type="button"
            onClick={loadActivity}
            style={{
              fontSize: 11,
              borderRadius: 999,
              border: "1px solid #4b5563",
              background: "#111827",
              padding: "2px 8px",
              cursor: "pointer",
            }}
          >
            Refresh
          </button>
        </div>
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

      <div style={{ maxHeight: 260, overflowY: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: 11,
          }}
        >
          <thead>
            <tr style={{ color: "#9ca3af", textAlign: "left" }}>
              <th style={{ padding: "4px 6px", borderBottom: "1px solid #1f2937" }}>
                Time
              </th>
              <th style={{ padding: "4px 6px", borderBottom: "1px solid #1f2937" }}>
                Object
              </th>
              <th style={{ padding: "4px 6px", borderBottom: "1px solid #1f2937" }}>
                Rule
              </th>
              <th style={{ padding: "4px 6px", borderBottom: "1px solid #1f2937" }}>
                Actions
              </th>
              <th style={{ padding: "4px 6px", borderBottom: "1px solid #1f2937" }}>
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {events.map((ev) => {
              const date = new Date(ev.timestamp);
              const statusColor =
                ev.status === "processed"
                  ? "#4ade80"
                  : ev.status === "pending"
                  ? "#fde68a"
                  : "#fca5a5";

              return (
                <tr key={ev.id}>
                  <td
                    style={{
                      padding: "4px 6px",
                      borderBottom: "1px solid #111827",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {date.toLocaleString()}
                  </td>
                  <td
                    style={{
                      padding: "4px 6px",
                      borderBottom: "1px solid #111827",
                      maxWidth: 240,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={`${ev.bucket}/${ev.object}`}
                  >
                    {ev.object}
                  </td>
                  <td
                    style={{
                      padding: "4px 6px",
                      borderBottom: "1px solid #111827",
                    }}
                  >
                    {ev.rule_name || "-"}
                  </td>
                  <td
                    style={{
                      padding: "4px 6px",
                      borderBottom: "1px solid #111827",
                      maxWidth: 180,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={ev.actions.join(", ")}
                  >
                    {ev.actions.join(", ")}
                  </td>
                  <td
                    style={{
                      padding: "4px 6px",
                      borderBottom: "1px solid #111827",
                    }}
                  >
                    <span
                      style={{
                        padding: "2px 6px",
                        borderRadius: 999,
                        border: "1px solid #374151",
                        color: statusColor,
                      }}
                    >
                      {ev.status}
                    </span>
                    {ev.status === "error" && ev.error_message && (
                      <span
                        style={{
                          marginLeft: 6,
                          color: "#fca5a5",
                        }}
                      >
                        ({ev.error_message})
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}

            {events.length === 0 && !loading && (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    padding: "8px 6px",
                    fontSize: 12,
                    color: "#6b7280",
                  }}
                >
                  No activity yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
