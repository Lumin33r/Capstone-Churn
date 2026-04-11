import { useState, useEffect, useRef } from "react";
import {
  Search, Phone, AlertTriangle, CheckCircle, XCircle,
  TrendingDown, TrendingUp, ArrowUpCircle, DollarSign,
  CreditCard, Wrench, User, FileText, Gift, Zap,
  BarChart3, Shield, Loader2, ChevronDown, Wifi,
  MessageSquare, Send, Upload, Mic, Clock, Play,
} from "lucide-react";

const CHURN_API_URL = import.meta.env.VITE_CHURN_API_URL || "http://localhost:8001";
const AGENT_API_URL = import.meta.env.VITE_AGENT_API_URL || "http://localhost:8000";

// ── Types ────────────────────────────────────────────────────────────

interface PredictResponse {
  churn_probability: number;
  prediction: string;
  risk_level: string;
  customer_id: string;
  has_call_data: boolean;
  qa_score: number;
  sentiment: string;
  emotion_frustration: number;
  emotion_anger: number;
  sentiment_shift: number;
  escalation_flag: number;
  resolution_flag: number;
}

interface ChatMessage {
  role: "user" | "agent";
  text: string;
  timestamp: Date;
}

interface Customer {
  id: string;
  label: string;
}

// ── Constants ────────────────────────────────────────────────────────

const RISK_STYLES: Record<string, { bg: string; border: string; text: string; bar: string; badge: string }> = {
  HIGH: { bg: "bg-red-100", border: "border-red-500", text: "text-red-700", bar: "bg-red-500", badge: "bg-red-600" },
  MEDIUM: { bg: "bg-amber-50", border: "border-amber-500", text: "text-amber-700", bar: "bg-amber-500", badge: "bg-amber-500" },
  LOW: { bg: "bg-green-50", border: "border-green-500", text: "text-green-700", bar: "bg-green-500", badge: "bg-green-600" },
};

const ACTION_INFO: Record<string, { icon: typeof ArrowUpCircle; desc: string }> = {
  PLAN_UPGRADE: { icon: ArrowUpCircle, desc: "Free upgrade to next tier for 3 months" },
  LOYALTY_DISCOUNT: { icon: DollarSign, desc: "15% off monthly bill for 6 months" },
  SERVICE_CREDIT: { icon: CreditCard, desc: "One-time $50 bill credit" },
  TECH_VISIT: { icon: Wrench, desc: "Priority technician visit within 24 hours" },
  DEDICATED_SUPPORT: { icon: User, desc: "Assign dedicated support representative" },
  CONTRACT_FLEX: { icon: FileText, desc: "Waive early termination fee" },
  FOLLOWUP_48H: { icon: Phone, desc: "Schedule follow-up call within 48 hours" },
  GOODWILL_CREDIT: { icon: Gift, desc: "One-time $20 bill credit" },
  SPEED_BOOST: { icon: Zap, desc: "Free speed boost trial for 1 month" },
  MONITOR: { icon: CheckCircle, desc: "No retention action needed" },
};

// ── Shared Components ────────────────────────────────────────────────

function ProgressBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.min(100, Math.round(value * 100));
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500 w-20">{label}</span>
      <div className="flex-1 bg-gray-200 rounded-full h-2.5">
        <div className={`${color} h-2.5 rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-600 w-10 text-right">{value.toFixed(2)}</span>
    </div>
  );
}

function RiskCard({ riskLevel, churnProbability }: { riskLevel: string | null; churnProbability: number | null }) {
  const styles = RISK_STYLES[riskLevel || "LOW"] || RISK_STYLES.LOW;
  const pct = Math.round((churnProbability || 0) * 100);
  return (
    <div className={`rounded-xl p-5 border-2 ${styles.bg} ${styles.border}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Churn Risk</h3>
        </div>
        <span className={`px-3 py-1 rounded-full text-white text-sm font-bold ${styles.badge}`}>{riskLevel}</span>
      </div>
      <div className={`text-4xl font-bold mb-3 ${styles.text}`}>{pct}%</div>
      <div className="w-full bg-gray-200 rounded-full h-3">
        <div className={`${styles.bar} h-3 rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function SentimentCard({ result }: { result: PredictResponse }) {
  const { qa_score: qaScore, sentiment, emotion_frustration: frustration,
    emotion_anger: anger, sentiment_shift: shift,
    escalation_flag, resolution_flag } = result;
  const escalated = escalation_flag === 1 ? "Yes" : "No";
  const resolved = resolution_flag === 1 ? "Yes" : "No";

  const sentimentColor: Record<string, string> = {
    Positive: "text-green-500", Neutral: "text-amber-500", Negative: "text-red-500",
  };

  return (
    <div className="rounded-xl p-5 bg-white border border-gray-200 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="w-4 h-4 text-gray-500" />
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Call Analysis</h3>
      </div>
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-3 h-3 rounded-full ${sentiment === "Positive" ? "bg-green-500" : sentiment === "Negative" ? "bg-red-500" : "bg-amber-500"}`} />
        <span className={`text-lg font-semibold ${sentimentColor[sentiment || ""] || "text-gray-400"}`}>{sentiment || "—"}</span>
        <span className="ml-auto text-2xl font-bold text-trilink-dark">{qaScore ? `${qaScore}/10` : "—"}</span>
      </div>
      <div className="space-y-2">
        {frustration !== null && <ProgressBar label="Frustration" value={frustration} color="bg-orange-500" />}
        {anger !== null && <ProgressBar label="Anger" value={anger} color="bg-red-500" />}
        {shift !== null && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 w-20">Shift</span>
            <div className="flex items-center gap-1">
              {shift < 0 ? <TrendingDown className="w-4 h-4 text-red-500" /> : <TrendingUp className="w-4 h-4 text-green-500" />}
              <span className={`text-sm font-semibold ${shift < 0 ? "text-red-600" : "text-green-600"}`}>{shift}</span>
            </div>
          </div>
        )}
      </div>
      <div className="flex gap-3 mt-4 pt-3 border-t border-gray-100">
        <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${escalated === "Yes" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"}`}>
          {escalated === "Yes" && <AlertTriangle className="w-3 h-3" />}
          {escalated === "Yes" ? "Escalated" : "Not Escalated"}
        </span>
        <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${resolved === "Yes" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
          {resolved === "Yes" ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {resolved === "Yes" ? "Resolved" : "Unresolved"}
        </span>
      </div>
    </div>
  );
}

const RISK_ACTIONS: Record<string, string> = { HIGH: "LOYALTY_DISCOUNT", MEDIUM: "FOLLOWUP_48H", LOW: "MONITOR" };

function ActionCard({ riskLevel }: { riskLevel: string | null }) {
  const action = RISK_ACTIONS[riskLevel || "LOW"] || "MONITOR";
  const info = ACTION_INFO[action];
  const ActionIcon = info?.icon || FileText;
  const desc = info?.desc || "";
  const isHighRisk = riskLevel === "HIGH";
  const recommendation = isHighRisk
    ? "Customer shows high churn risk. Recommend immediate outreach with retention offer."
    : riskLevel === "MEDIUM"
    ? "Customer shows moderate risk. Schedule proactive follow-up."
    : "Customer appears stable. Continue monitoring.";

  return (
    <div className={`rounded-xl p-5 border shadow-sm ${isHighRisk ? "bg-red-50 border-red-300" : "bg-white border-gray-200"}`}>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Recommended Action</h3>
      <div className="flex items-center gap-3 mb-2">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isHighRisk ? "bg-red-200" : "bg-trilink-light/10"}`}>
          <ActionIcon className={`w-5 h-5 ${isHighRisk ? "text-red-700" : "text-trilink-dark"}`} />
        </div>
        <div>
          <span className="font-bold text-gray-800 text-lg">{action.replace(/_/g, " ")}</span>
          <p className="text-sm text-gray-500">{desc}</p>
        </div>
      </div>
      <p className="mt-3 text-sm text-gray-700 bg-gray-50 rounded-lg p-3 border border-gray-100">{recommendation}</p>
      {isHighRisk && (
        <div className="mt-3 flex items-center gap-2 text-red-700 bg-red-100 rounded-lg p-3 text-sm font-semibold">
          <AlertTriangle className="w-4 h-4" /> IMMEDIATE MANAGER REVIEW REQUIRED
        </div>
      )}
    </div>
  );
}

function CustomerCombobox({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [allCustomers, setAllCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function loadCustomers() {
      try {
        const res = await fetch(`${CHURN_API_URL}/customers?limit=100`);
        if (res.ok) setAllCustomers(await res.json());
      } catch { /* backend not running */ }
      setLoading(false);
    }
    loadCustomers();
  }, []);

  const filtered = query
    ? allCustomers.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
    : allCustomers;

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <label className="block text-sm font-medium text-gray-700 mb-1">Customer</label>
      <div className="relative">
        <input
          type="text"
          className="w-full border border-gray-300 rounded-lg pl-3 pr-8 py-2 text-sm focus:ring-2 focus:ring-trilink-light focus:border-transparent outline-none"
          placeholder={loading ? "Loading customers..." : "Select or search customer..."}
          value={query || value || ""}
          onChange={(e) => {
            const val = e.target.value;
            setQuery(val);
            setOpen(true);
            if (/^C\d{8}$/.test(val)) { onChange(val); } else { onChange(""); }
          }}
          onFocus={() => { setQuery(""); setOpen(true); }}
          disabled={loading}
        />
        <ChevronDown className="absolute right-2 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
      </div>
      {open && filtered.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {filtered.slice(0, 20).map((c) => (
            <li key={c.id} className="px-3 py-2 text-sm hover:bg-trilink-light/10 cursor-pointer border-b border-gray-50 last:border-0"
              onClick={() => { onChange(c.id); setQuery(c.label); setOpen(false); }}>
              {c.label}
            </li>
          ))}
          {filtered.length > 20 && (
            <li className="px-3 py-2 text-xs text-gray-400 text-center">{filtered.length - 20} more — type to filter</li>
          )}
        </ul>
      )}
    </div>
  );
}

// ── Analyze Tab ──────────────────────────────────────────────────────

function AnalyzeTab() {
  const [customerId, setCustomerId] = useState("");
  const [transcript, setTranscript] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    if (!customerId) { setError("Select a customer ID"); return; }
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await fetch(`${CHURN_API_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_id: customerId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || `API error: ${res.status}`);
      }
      setResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally { setLoading(false); }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Phone className="w-4 h-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Call Analysis</h2>
          </div>
          <CustomerCombobox value={customerId} onChange={setCustomerId} />
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Call Transcript <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm h-64 resize-none focus:ring-2 focus:ring-trilink-light focus:border-transparent outline-none"
              placeholder="Paste call transcript here, or leave empty to predict from account data only..."
              value={transcript} onChange={(e) => setTranscript(e.target.value)}
            />
          </div>
          <button onClick={handleAnalyze} disabled={loading || !customerId}
            className={`w-full mt-4 py-3 px-4 rounded-lg text-white font-semibold text-sm transition-all cursor-pointer flex items-center justify-center gap-2 ${
              loading || !customerId ? "bg-gray-300 cursor-not-allowed" : "bg-trilink-dark hover:bg-trilink-mid shadow-md hover:shadow-lg"
            }`}>
            {loading ? (<><Loader2 className="w-4 h-4 animate-spin" />Analyzing...</>) : (<><Search className="w-4 h-4" />Analyze Call</>)}
          </button>
          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}
        </div>
      </div>
      <div className="lg:col-span-3 space-y-4">
        {result ? (
          <>
            <RiskCard riskLevel={result.risk_level} churnProbability={result.churn_probability} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <SentimentCard result={result} />
              <ActionCard riskLevel={result.risk_level} />
            </div>
          </>
        ) : (
          <div className="rounded-xl border-2 border-dashed border-gray-300 bg-white p-16 text-center">
            <BarChart3 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-400">No Analysis Yet</h3>
            <p className="text-sm text-gray-400 mt-1">Select a customer and click Analyze Call to see results</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Chat Tab ─────────────────────────────────────────────────────────

function ChatTab() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "agent", text: "Hello! I'm the TriLink Retention Engine AI. I can help you:\n\n- Analyze churn risk for a customer (e.g., \"What's the risk for C00036458?\")\n- Show high-risk customers (e.g., \"Show me my top 5 high risk customers\")\n- Analyze a call transcript\n\nHow can I help you today?", timestamp: new Date() },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    if (!input.trim() || loading) return;
    const userMsg: ChatMessage = { role: "user", text: input.trim(), timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const cidMatch = input.match(/C\d{8}/);
    const customerId = cidMatch ? cidMatch[0] : undefined;
    const lowerInput = input.toLowerCase();

    try {
      let agentText: string;

      // Try agent service first
      try {
        const res = await fetch(`${AGENT_API_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: input.trim(), customer_id: customerId }),
        });
        if (res.ok) {
          const data = await res.json();
          agentText = data.response || "Analysis complete.";
          setMessages((prev) => [...prev, { role: "agent", text: agentText, timestamp: new Date() }]);
          return;
        }
      } catch {
        // Agent service not running — fall through to direct API calls
      }

      // Fallback: call churn predictor directly
      if (customerId) {
        const res = await fetch(`${CHURN_API_URL}/predict`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ customer_id: customerId }),
        });
        if (res.ok) {
          const data: PredictResponse = await res.json();
          const risk = data.risk_level;
          const pct = Math.round(data.churn_probability * 100);
          agentText = `Customer ${data.customer_id}\n\n` +
            `Churn Risk: ${risk} (${pct}%)\n` +
            `QA Score: ${data.qa_score}/10\n` +
            `Sentiment: ${data.sentiment}\n` +
            `Frustration: ${data.emotion_frustration.toFixed(2)} | Anger: ${data.emotion_anger.toFixed(2)}\n` +
            `Sentiment Shift: ${data.sentiment_shift}\n` +
            `Escalated: ${data.escalation_flag ? "Yes" : "No"} | Resolved: ${data.resolution_flag ? "Yes" : "No"}\n` +
            `Call Data: ${data.has_call_data ? "Yes" : "No (using neutral defaults)"}\n\n` +
            (risk === "HIGH" ? "This customer is at high risk of churning. Recommended action: LOYALTY DISCOUNT — 15% off for 6 months. IMMEDIATE MANAGER REVIEW REQUIRED." :
             risk === "MEDIUM" ? "This customer shows moderate risk. Recommended: FOLLOW-UP call within 48 hours." :
             "This customer appears stable. Continue monitoring.");
        } else {
          agentText = "I couldn't find that customer. Please check the ID and try again.";
        }
      } else if (lowerInput.includes("high risk") || lowerInput.includes("who should") || lowerInput.includes("top customer") || lowerInput.includes("leaderboard")) {
        const res = await fetch(`${CHURN_API_URL}/high-risk?limit=5`);
        if (res.ok) {
          const data = await res.json();
          if (data.length > 0) {
            agentText = "Top High-Risk Customers:\n\n" +
              data.map((c: Record<string, unknown>, i: number) =>
                `${i + 1}. ${c.customer_id} — ${Math.round((c.churn_probability as number) * 100)}% risk | ${c.plan} $${c.monthly_cost}/mo | ${c.sentiment} | QA ${c.qa_score}/10`
              ).join("\n") +
              "\n\nThese customers should be prioritized for retention outreach.";
          } else {
            agentText = "No high-risk customers found at this time.";
          }
        } else {
          agentText = "The high-risk query is processing. This can take a minute for the first request — try again shortly.";
        }
      } else {
        agentText = "I can help you with:\n\n" +
          "- Check a customer: \"What's the risk for C00036458?\"\n" +
          "- High-risk list: \"Show me high risk customers\"\n" +
          "- Analyze a transcript: paste it with a customer ID";
      }

      setMessages((prev) => [...prev, { role: "agent", text: agentText, timestamp: new Date() }]);
    } catch {
      setMessages((prev) => [...prev, { role: "agent", text: "Sorry, I'm having trouble connecting. Please check that the churn predictor API is running on port 8001.", timestamp: new Date() }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col" style={{ height: "calc(100vh - 200px)" }}>
        {/* Chat messages */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-xl px-4 py-3 ${
                msg.role === "user"
                  ? "bg-trilink-dark text-white rounded-br-sm"
                  : "bg-gray-100 text-gray-800 rounded-bl-sm"
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  {msg.role === "agent" && <Wifi className="w-3 h-3 text-trilink-light" />}
                  <span className="text-xs opacity-60">
                    {msg.role === "agent" ? "Retention Engine AI" : "You"} — {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <div className="text-sm whitespace-pre-wrap">{msg.text}</div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 rounded-xl px-4 py-3 rounded-bl-sm">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-trilink-light" />
                  <span className="text-sm text-gray-500">Analyzing...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-trilink-light focus:border-transparent outline-none"
              placeholder="Ask about a customer, request high-risk list, or paste a transcript..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              disabled={loading}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className={`px-4 py-2.5 rounded-lg text-white transition-all flex items-center gap-2 ${
                loading || !input.trim() ? "bg-gray-300 cursor-not-allowed" : "bg-trilink-dark hover:bg-trilink-mid cursor-pointer"
              }`}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Try: "What's the churn risk for C00036458?" or "Show me high risk customers"
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Transcribe Tab ──────────────────────────────────────────────────

interface TranscriptMeta {
  name: string;
  key: string;
  size: number;
  last_modified: string;
}

interface TranscriptDetail {
  filename: string;
  transcript: string;
  segments: { speaker: string; text: string }[];
  job_name: string;
}

function TranscribeTab() {
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [transcripts, setTranscripts] = useState<TranscriptMeta[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [selectedTranscript, setSelectedTranscript] = useState<TranscriptDetail | null>(null);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function loadTranscripts() {
    setLoadingList(true);
    try {
      const res = await fetch(`${CHURN_API_URL}/transcripts`);
      if (res.ok) setTranscripts(await res.json());
    } catch {
      setError("Could not load transcripts. Is the API running?");
    }
    setLoadingList(false);
  }

  useEffect(() => { loadTranscripts(); }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError(null); setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${CHURN_API_URL}/transcribe`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail);
      }
      const data = await res.json();
      setUploadResult(`Uploaded ${data.filename}. Transcription job started — check back in 1-2 minutes.`);
      // Refresh list after a short delay
      setTimeout(loadTranscripts, 5000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function viewTranscript(name: string) {
    setLoadingTranscript(true); setSelectedTranscript(null);
    try {
      const res = await fetch(`${CHURN_API_URL}/transcripts/${name}`);
      if (res.ok) setSelectedTranscript(await res.json());
      else setError("Could not load transcript");
    } catch {
      setError("Failed to fetch transcript");
    }
    setLoadingTranscript(false);
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left: Upload + List */}
      <div className="lg:col-span-1 space-y-4">
        {/* Upload Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Mic className="w-4 h-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Upload Audio</h2>
          </div>
          <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-trilink-light transition-colors cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
          >
            <Upload className={`w-10 h-10 mx-auto mb-3 ${uploading ? "text-trilink-light animate-pulse" : "text-gray-300"}`} />
            <p className="text-sm text-gray-500">
              {uploading ? "Uploading..." : "Click to upload audio file"}
            </p>
            <p className="text-xs text-gray-400 mt-1">.wav, .mp3, .mp4, .flac</p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".wav,.mp3,.mp4,.flac"
            className="hidden"
            onChange={handleUpload}
          />
          {uploadResult && (
            <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700 flex items-center gap-2">
              <CheckCircle className="w-4 h-4 shrink-0" />{uploadResult}
            </div>
          )}
          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}
        </div>

        {/* Transcript List */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-gray-500" />
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Transcripts</h2>
            </div>
            <button
              onClick={loadTranscripts}
              disabled={loadingList}
              className="text-xs text-trilink-dark hover:text-trilink-light transition-colors cursor-pointer"
            >
              {loadingList ? <Loader2 className="w-3 h-3 animate-spin" /> : "Refresh"}
            </button>
          </div>
          {transcripts.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">No transcripts yet</p>
          ) : (
            <ul className="space-y-2">
              {transcripts.map((t) => (
                <li
                  key={t.key}
                  onClick={() => viewTranscript(t.name)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all hover:border-trilink-light ${
                    selectedTranscript?.filename === t.name
                      ? "border-trilink-light bg-trilink-light/5"
                      : "border-gray-100 hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Play className="w-3 h-3 text-gray-400" />
                    <span className="text-sm font-medium text-gray-700 truncate">{t.name}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <Clock className="w-3 h-3 text-gray-300" />
                    <span className="text-xs text-gray-400">
                      {new Date(t.last_modified).toLocaleDateString()} {new Date(t.last_modified).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    <span className="text-xs text-gray-300 ml-auto">{(t.size / 1024).toFixed(1)} KB</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Right: Transcript Viewer */}
      <div className="lg:col-span-2">
        {loadingTranscript ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-16 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-trilink-light mx-auto mb-3" />
            <p className="text-sm text-gray-500">Loading transcript...</p>
          </div>
        ) : selectedTranscript ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
            <div className="flex items-center gap-2 mb-4">
              <FileText className="w-4 h-4 text-gray-500" />
              <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
                {selectedTranscript.filename}
              </h2>
              {selectedTranscript.job_name && (
                <span className="text-xs text-gray-400 ml-auto">Job: {selectedTranscript.job_name}</span>
              )}
            </div>

            {/* Speaker segments */}
            {selectedTranscript.segments.length > 0 ? (
              <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto">
                {selectedTranscript.segments.map((seg, i) => (
                  <div key={i} className={`flex ${seg.speaker === "spk_0" ? "justify-start" : "justify-end"}`}>
                    <div className={`max-w-[80%] rounded-xl px-4 py-3 ${
                      seg.speaker === "spk_0"
                        ? "bg-blue-50 text-blue-900 rounded-bl-sm"
                        : "bg-gray-100 text-gray-800 rounded-br-sm"
                    }`}>
                      <span className="text-xs font-semibold block mb-1">
                        {seg.speaker === "spk_0" ? "Agent" : "Customer"}
                      </span>
                      <p className="text-sm">{seg.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              /* Full transcript fallback */
              <div className="bg-gray-50 rounded-lg p-4 max-h-[calc(100vh-300px)] overflow-y-auto">
                <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {selectedTranscript.transcript}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border-2 border-dashed border-gray-300 bg-white p-16 text-center">
            <Mic className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-400">No Transcript Selected</h3>
            <p className="text-sm text-gray-400 mt-1">Upload an audio file or select a transcript from the list</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main App ─────────────────────────────────────────────────────────

export default function App() {
  const [tab, setTab] = useState<"analyze" | "chat" | "transcribe">("analyze");

  return (
    <div className="min-h-screen bg-slate-100">
      {/* Header */}
      <header className="bg-trilink-dark text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-trilink-light rounded-lg flex items-center justify-center">
              <Wifi className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">TriLink Retention Engine</h1>
              <p className="text-xs text-trilink-light/70">Customer Intelligence Platform</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {/* Tab switcher */}
            <div className="flex bg-trilink-mid/50 rounded-lg p-0.5">
              <button
                onClick={() => setTab("analyze")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "analyze" ? "bg-white text-trilink-dark shadow-sm" : "text-white/70 hover:text-white"
                }`}
              >
                <BarChart3 className="w-3.5 h-3.5" /> Analyze
              </button>
              <button
                onClick={() => setTab("chat")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "chat" ? "bg-white text-trilink-dark shadow-sm" : "text-white/70 hover:text-white"
                }`}
              >
                <MessageSquare className="w-3.5 h-3.5" /> Chat
              </button>
              <button
                onClick={() => setTab("transcribe")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "transcribe" ? "bg-white text-trilink-dark shadow-sm" : "text-white/70 hover:text-white"
                }`}
              >
                <Mic className="w-3.5 h-3.5" /> Transcribe
              </button>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-300">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              System Online
            </div>
          </div>
        </div>
      </header>

      {/* Main — both tabs stay mounted to preserve state */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        <div className={tab === "analyze" ? "" : "hidden"}><AnalyzeTab /></div>
        <div className={tab === "chat" ? "" : "hidden"}><ChatTab /></div>
        <div className={tab === "transcribe" ? "" : "hidden"}><TranscribeTab /></div>
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-6 py-4 text-center text-xs text-gray-400">
        TriLink Telecom &bull; Retention Engine v1.0 &bull; Internal Use Only
      </footer>
    </div>
  );
}
