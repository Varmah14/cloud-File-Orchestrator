import { UploadPanel } from "./components/UploadPanel";
import { RulesPage } from "./pages/RulesPage";
import { ActivityPanel } from "./components/ActivityPanel";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#050816",
        color: "#e5e7eb",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
      }}
    >
      <header
        style={{
          borderBottom: "1px solid #1f2933",
          padding: "12px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontSize: 18, fontWeight: 600 }}>
            Cloud File Orchestrator
          </span>
          <span style={{ fontSize: 12, color: "#9ca3af" }}>Admin Console</span>
        </div>
        <span style={{ fontSize: 11, color: "#6b7280" }}>
          API: {API_BASE}
        </span>
      </header>

      <main style={{ padding: 20, maxWidth: 1100, margin: "0 auto" }}>
        <section style={{ marginBottom: 24 }}>
          <UploadPanel apiBase={API_BASE} />
        </section>

        <section style={{ marginBottom: 24 }}>
          <RulesPage apiBase={API_BASE} />
        </section>

        <section>
          <ActivityPanel apiBase={API_BASE} />
        </section>
      </main>
    </div>
  );
}

export default App;
