import { useState, useEffect, useRef } from "react";
import {
  Search, Phone, AlertTriangle, CheckCircle, XCircle,
  TrendingDown, TrendingUp, ArrowUpCircle, DollarSign,
  CreditCard, Wrench, User, FileText, Gift, Zap,
  BarChart3, Shield, Loader2, ChevronDown, Wifi,
} from "lucide-react";

const AGENT_API_URL = import.meta.env.VITE_AGENT_API_URL || "http://localhost:8000";
const CHURN_API_URL = import.meta.env.VITE_CHURN_API_URL || "http://localhost:8001";

interface ChatResponse {
  response: string;
  customer_id: string | null;
  qa_score: number | null;
  sentiment: string | null;
  churn_probability: number | null;
  risk_level: string | null;
  retention_recommendation: string | null;
}

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

function SentimentCard({ qaScore, sentiment, response }: { qaScore: number | null; sentiment: string | null; response: string }) {
  const frustMatch = response.match(/Frustration:\s*([\d.]+)/);
  const angerMatch = response.match(/Anger:\s*([\d.]+)/);
  const shiftMatch = response.match(/Sentiment Shift:\s*([-\d.]+)/);
  const escalatedMatch = response.match(/Escalated:\s*(Yes|No)/);
  const resolvedMatch = response.match(/Resolved:\s*(Yes|No)/);

  const frustration = frustMatch ? parseFloat(frustMatch[1]) : null;
  const anger = angerMatch ? parseFloat(angerMatch[1]) : null;
  const shift = shiftMatch ? parseFloat(shiftMatch[1]) : null;
  const escalated = escalatedMatch ? escalatedMatch[1] : null;
  const resolved = resolvedMatch ? resolvedMatch[1] : null;

  const sentimentColor: Record<string, string> = {
    Positive: "text-green-500",
    Neutral: "text-amber-500",
    Negative: "text-red-500",
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
      {(escalated || resolved) && (
        <div className="flex gap-3 mt-4 pt-3 border-t border-gray-100">
          {escalated && (
            <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${escalated === "Yes" ? "bg-red-100 text-red-700" : "bg-gray-100 text-gray-600"}`}>
              {escalated === "Yes" && <AlertTriangle className="w-3 h-3" />}
              {escalated === "Yes" ? "Escalated" : "Not Escalated"}
            </span>
          )}
          {resolved && (
            <span className={`text-xs px-2 py-1 rounded-full flex items-center gap-1 ${resolved === "Yes" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
              {resolved === "Yes" ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
              {resolved === "Yes" ? "Resolved" : "Unresolved"}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function ActionCard({ response, riskLevel }: { response: string; riskLevel: string | null }) {
  const actionMatch = response.match(/Action:\s*(\S+)/);
  const recMatch = response.match(/Recommendation:\s*(.+?)(?:\n|---)/s);
  const action = actionMatch ? actionMatch[1] : null;
  const recommendation = recMatch ? recMatch[1].trim() : null;

  const info = ACTION_INFO[action || ""];
  const ActionIcon = info?.icon || FileText;
  const desc = info?.desc || action || "";
  const isHighRisk = riskLevel === "HIGH";

  return (
    <div className={`rounded-xl p-5 border shadow-sm ${isHighRisk ? "bg-red-50 border-red-300" : "bg-white border-gray-200"}`}>
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Recommended Action</h3>
      {action ? (
        <>
          <div className="flex items-center gap-3 mb-2">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isHighRisk ? "bg-red-200" : "bg-trilink-light/10"}`}>
              <ActionIcon className={`w-5 h-5 ${isHighRisk ? "text-red-700" : "text-trilink-dark"}`} />
            </div>
            <div>
              <span className="font-bold text-gray-800 text-lg">{action.replace(/_/g, " ")}</span>
              <p className="text-sm text-gray-500">{desc}</p>
            </div>
          </div>
          {recommendation && (
            <p className="mt-3 text-sm text-gray-700 bg-gray-50 rounded-lg p-3 border border-gray-100">{recommendation}</p>
          )}
          {isHighRisk && (
            <div className="mt-3 flex items-center gap-2 text-red-700 bg-red-100 rounded-lg p-3 text-sm font-semibold">
              <AlertTriangle className="w-4 h-4" />
              IMMEDIATE MANAGER REVIEW REQUIRED
            </div>
          )}
        </>
      ) : (
        <p className="text-gray-400 italic">Run analysis to see recommendations</p>
      )}
    </div>
  );
}

interface Customer {
  id: string;
  label: string;
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
      } catch { /* backend not running yet */ }
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
          onChange={(e) => { setQuery(e.target.value); setOpen(true); onChange(""); }}
          onFocus={() => setOpen(true)}
          disabled={loading}
        />
        <ChevronDown className="absolute right-2 top-2.5 w-4 h-4 text-gray-400 pointer-events-none" />
      </div>
      {open && filtered.length > 0 && (
        <ul className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {filtered.slice(0, 20).map((c) => (
            <li
              key={c.id}
              className="px-3 py-2 text-sm hover:bg-trilink-light/10 cursor-pointer border-b border-gray-50 last:border-0"
              onClick={() => { onChange(c.id); setQuery(c.label); setOpen(false); }}
            >
              {c.label}
            </li>
          ))}
          {filtered.length > 20 && (
            <li className="px-3 py-2 text-xs text-gray-400 text-center">
              {filtered.length - 20} more — type to filter
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

export default function App() {
  const [customerId, setCustomerId] = useState("");
  const [transcript, setTranscript] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    if (!customerId) { setError("Select a customer ID"); return; }
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const message = transcript
        ? `Analyze this call transcript for customer ${customerId}:\n\n${transcript}`
        : `Predict churn risk for customer ${customerId} (no transcript available)`;

      const res = await fetch(`${AGENT_API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, customer_id: customerId }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data: ChatResponse = await res.json();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

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
          <div className="flex items-center gap-2 text-sm text-gray-300">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            System Online
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

          {/* Left Panel */}
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
                  value={transcript}
                  onChange={(e) => setTranscript(e.target.value)}
                />
              </div>

              <button
                onClick={handleAnalyze}
                disabled={loading || !customerId}
                className={`w-full mt-4 py-3 px-4 rounded-lg text-white font-semibold text-sm transition-all cursor-pointer flex items-center justify-center gap-2 ${
                  loading || !customerId
                    ? "bg-gray-300 cursor-not-allowed"
                    : "bg-trilink-dark hover:bg-trilink-mid shadow-md hover:shadow-lg"
                }`}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Analyze Call
                  </>
                )}
              </button>

              {error && (
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  {error}
                </div>
              )}
            </div>
          </div>

          {/* Right Panel */}
          <div className="lg:col-span-3 space-y-4">
            {result ? (
              <>
                <RiskCard riskLevel={result.risk_level} churnProbability={result.churn_probability} />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <SentimentCard qaScore={result.qa_score} sentiment={result.sentiment} response={result.response} />
                  <ActionCard response={result.response} riskLevel={result.risk_level} />
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
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-6 py-4 text-center text-xs text-gray-400">
        TriLink Telecom &bull; Retention Engine v1.0 &bull; Internal Use Only
      </footer>
    </div>
  );
}
