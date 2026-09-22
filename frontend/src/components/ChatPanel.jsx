import { useState } from "react";
import { askCoach } from "../api.js";
import { useUnits } from "../UnitContext.jsx";
import { colors } from "../theme.js";

const EXAMPLES = [
  "What's my workout today?",
  "Am I ramping up too fast?",
  "What phase am I in and when do I peak?",
  "How much should I squat this week?",
];

// Chat panel: talk to the coach agent. Shows which tools it used, so you can
// literally see the agent retrieving data — a nice thing to demo.
export default function ChatPanel() {
  const { system } = useUnits();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send(text) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const res = await askCoach(q, [], system);
      setMessages((m) => [...m, { role: "coach", text: res.reply, tools: res.tool_calls }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "coach", text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card" style={{ position: "sticky", top: 16, display: "flex",
         flexDirection: "column", height: "calc(100vh - 130px)", minHeight: 420 }}>
      <h2 style={{ marginBottom: 10 }}>Ask your coach</h2>

      <div style={{ flex: 1, overflowY: "auto", border: `1px solid ${colors.border}`,
                    borderRadius: 8, padding: 12, marginBottom: 10, background: colors.card }}>
        {messages.length === 0 && (
          <div>
            <p className="muted" style={{ marginTop: 0 }}>Try asking:</p>
            {EXAMPLES.map((ex) => (
              <button key={ex} className="btn" style={{ display: "block", width: "100%",
                       textAlign: "left", marginBottom: 6, fontWeight: 500 }}
                      onClick={() => send(ex)}>
                {ex}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 14 }}>
            <div style={{ fontWeight: 700, fontSize: 11, textTransform: "uppercase",
                          letterSpacing: "0.03em",
                          color: m.role === "user" ? colors.muted : colors.forest }}>
              {m.role === "user" ? "You" : "Coach"}
            </div>
            <div style={{ whiteSpace: "pre-wrap", fontSize: 14 }}>{m.text}</div>
            {m.tools && m.tools.length > 0 && (
              <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>
                🔧 {m.tools.join(", ")}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="muted">Coach is thinking…</div>}
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about your training…"
          style={{ flex: 1, padding: 9, borderRadius: 8, border: `1px solid ${colors.border}`, fontSize: 14 }}
        />
        <button className="btn btn-primary" onClick={() => send()} disabled={loading}>Send</button>
      </div>
    </div>
  );
}
