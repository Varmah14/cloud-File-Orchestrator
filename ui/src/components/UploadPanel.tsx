import { useState } from "react";

interface UploadPanelProps {
  apiBase: string;
}

interface UploadResponse {
  message: string;
  bucket: string;
  object: string;
  content_type: string;
  public_url?: string;
}

export function UploadPanel({ apiBase }: UploadPanelProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Please choose a file to upload.");
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(`${apiBase}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed with ${res.status}`);
      }

      const data = (await res.json()) as UploadResponse;
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div
      style={{
        border: "1px solid #1f2937",
        borderRadius: 10,
        padding: 16,
        background: "#0b1020",
      }}
    >
      <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
        Upload file
      </h2>
      <p style={{ fontSize: 12, color: "#9ca3af", marginBottom: 12 }}>
        Upload a file to your GCS bucket. GCS notifications automatically trigger
        your pipeline (inspect → classify → act).
      </p>

      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", flexDirection: "column", gap: 8 }}
      >
        <input
          type="file"
          onChange={(e) => {
            const f = e.target.files?.[0] || null;
            setFile(f);
            setResult(null);
            setError(null);
          }}
          style={{ fontSize: 12 }}
        />

        <button
          type="submit"
          disabled={!file || uploading}
          style={{
            marginTop: 4,
            alignSelf: "flex-start",
            padding: "6px 12px",
            fontSize: 12,
            borderRadius: 6,
            border: "1px solid #374151",
            background: "#111827",
            cursor: !file || uploading ? "not-allowed" : "pointer",
            opacity: !file || uploading ? 0.5 : 1,
          }}
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </form>

      {error && (
        <div
          style={{
            marginTop: 10,
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

      {result && (
        <div
          style={{
            marginTop: 10,
            fontSize: 12,
            color: "#bbf7d0",
            borderRadius: 6,
            padding: "6px 8px",
            background: "#064e3b",
          }}
        >
          <div>Message: {result.message}</div>
          <div>Bucket: {result.bucket}</div>
          <div>Object: {result.object}</div>
          <div>Content-Type: {result.content_type}</div>
          {result.public_url && (
            <div>
              URL:{" "}
              <a
                href={result.public_url}
                target="_blank"
                rel="noreferrer"
                style={{ color: "#a5b4fc" }}
              >
                {result.public_url}
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
