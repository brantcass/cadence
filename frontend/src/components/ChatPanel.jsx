import { useState } from "react";
import { askCoach } from "../api.js";

// Chat panel: talk to the coach agent. Shows which tools it used, so you can
// literally see the agent retrieving data — a nice thing to demo.
export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const res = await askCoach(q);
      setMessages((m) => [
        ...m,
        { role: "coach", text: res.reply, tools: res.tool_calls },
      ]);
    } catch (e) {
      setMessages((m) => [...m, { role: "coach", text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={{ display: "flex", flexDirection: "column", height: 520 }}>
      <h2>Ask your coach</h2>
      <div style={{ flex: 1, overflowY: "auto", border: "1px solid #eee",
                    borderRadius: 8, padding: 12, marginBottom: 8 }}>
        {messages.length === 0 && (
          <p style={{ color: "#999" }}>
            Try: "Am I overtraining?" or "What should tomorrow's workout be?"
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, fontSize: 12, color: "#888" }}>
              {m.role === "user" ? "You" : "Coach"}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div>
            {m.tools && m.tools.length > 0 && (
              <div style={{ fontSize: 11, color: "#aaa", marginTop: 2 }}>
                used: {m.tools.join(", ")}
              </div>
            )}
          </div>
        ))}
        {loading && <div style={{ color: "#999" }}>Coach is thinking…</div>}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about your training…"
          style={{ flex: 1, padding: 8, borderRadius: 6, border: "1px solid #ccc" }}
        />
        <button onClick={send} disabled={loading}
                style={{ padding: "8px 16px", borderRadius: 6 }}>
          Send
        </button>
      </div>
    </section>
  );
}
