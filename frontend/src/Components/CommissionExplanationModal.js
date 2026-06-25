import { useCallback, useEffect, useState } from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import IconButton from "@mui/material/IconButton";
import CloseIcon from "@mui/icons-material/Close";
import api, { getApiErrorMessage } from "../api";
import { formatMoney } from "../utils/currency";
import "./commissionExplanation.css";

function monthBounds(dateStr) {
  if (!dateStr) return null;
  const parsed = new Date(`${dateStr}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  const year = parsed.getFullYear();
  const month = parsed.getMonth();
  const lastDay = new Date(year, month + 1, 0).getDate();
  const pad = (n) => String(n).padStart(2, "0");
  return {
    start: `${year}-${pad(month + 1)}-01`,
    end: `${year}-${pad(month + 1)}-${pad(lastDay)}`,
  };
}

function resolveWhatIfPeriod(periodStart, periodEnd, explanation) {
  if (periodStart && periodEnd) {
    return { start: periodStart, end: periodEnd };
  }
  const fromOrder = monthBounds(explanation?.order_date);
  if (fromOrder) return fromOrder;
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();
  const lastDay = new Date(year, month + 1, 0).getDate();
  const pad = (n) => String(n).padStart(2, "0");
  return {
    start: `${year}-${pad(month + 1)}-01`,
    end: `${year}-${pad(month + 1)}-${pad(lastDay)}`,
  };
}

function CommissionExplanationModal({
  open,
  onClose,
  commissionId,
  periodStart,
  periodEnd,
}) {
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [answerSource, setAnswerSource] = useState("");
  const [asking, setAsking] = useState(false);
  const [whatIfAmount, setWhatIfAmount] = useState("50000");
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [simulating, setSimulating] = useState(false);

  const loadExplanation = useCallback(async () => {
    if (!commissionId) return;
    setLoading(true);
    setError("");
    setAnswer("");
    try {
      const res = await api.get(`commissions/${commissionId}/explanation/`);
      setExplanation(res.data);
    } catch (err) {
      setExplanation(null);
      setError(err.response?.data?.error || "Could not load explanation.");
    } finally {
      setLoading(false);
    }
  }, [commissionId]);

  useEffect(() => {
    if (open && commissionId) {
      loadExplanation();
      setWhatIfResult(null);
    }
    if (!open) {
      setExplanation(null);
      setAnswer("");
      setAnswerSource("");
      setQuestion("");
      setWhatIfResult(null);
    }
  }, [open, commissionId, loadExplanation]);

  const askQuestion = async (event) => {
    event.preventDefault();
    if (!commissionId || !question.trim()) return;
    setAsking(true);
    setAnswer("");
    setAnswerSource("");
    const aiTimeoutMs = parseInt(
      process.env.REACT_APP_AI_REQUEST_TIMEOUT_MS || "180000",
      10
    );
    try {
      const res = await api.post(
        `commissions/${commissionId}/explanation/ask/`,
        { question: question.trim() },
        { timeout: aiTimeoutMs }
      );
      setAnswer(res.data.answer || "");
      setAnswerSource(res.data.source || "");
    } catch (err) {
      const message =
        err.code === "ECONNABORTED"
          ? "The AI took too long (local Ollama can take up to a minute on the first question). Please try again — keep the Ollama app running."
          : getApiErrorMessage(err, "Could not answer that question.");
      setAnswer(message);
      setAnswerSource("error");
    } finally {
      setAsking(false);
    }
  };

  const runWhatIf = async (event) => {
    event.preventDefault();
    const period = resolveWhatIfPeriod(periodStart, periodEnd, explanation);
    if (!period?.start || !period?.end) {
      setWhatIfResult({ error: "Could not determine a date range for simulation." });
      return;
    }
    setSimulating(true);
    setWhatIfResult(null);
    try {
      const res = await api.post("commissions/what-if/", {
        extra_sales: whatIfAmount,
        start_date: period.start,
        end_date: period.end,
      });
      setWhatIfResult(res.data);
    } catch (err) {
      setWhatIfResult({
        error:
          err.response?.data?.error ||
          err.response?.data?.detail ||
          "Simulation failed.",
      });
    } finally {
      setSimulating(false);
    }
  };

  const aiConfigured = explanation?.ai?.configured === true;
  const aiSetupMessage = explanation?.ai?.message;

  const suggestedQuestions = [
    "How was this calculated?",
    "How can I earn more next month?",
    "What is my quota attainment?",
    "When will this be paid?",
  ];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth className="ce-dialog">
      <DialogTitle className="ce-dialog__title">
        <span>Commission explanation</span>
        <IconButton aria-label="Close" onClick={onClose} size="small">
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent className="ce-dialog__body">
        {loading && <p className="ce-muted">Loading breakdown…</p>}
        {error && <p className="ce-error">{error}</p>}

        {explanation && !loading && (
          <>
            <div className="ce-hero">
              <p className="ce-hero__label">Commission earned</p>
              <p className="ce-hero__amount">
                {formatMoney(explanation.commission_earned, explanation.currency)}
              </p>
              <p className="ce-hero__meta">
                Order {explanation.order_id || "—"}
              </p>
            </div>

            <section className="ce-section">
              <h3 className="ce-section__title">Why?</h3>
              <ul className="ce-lines">
                {explanation.lines?.map((line) => (
                  <li
                    key={line.key}
                    className={`ce-line${line.highlight ? " ce-line--highlight" : ""}`}
                  >
                    <span className="ce-line__check" aria-hidden="true">
                      ✓
                    </span>
                    <div className="ce-line__body">
                      <span className="ce-line__label">{line.label}</span>
                      <span className="ce-line__value">{line.display}</span>
                      {line.detail && (
                        <span className="ce-line__detail">{line.detail}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
              {explanation.summary && (
                <p className="ce-summary">{explanation.summary}</p>
              )}
            </section>

            <section className="ce-section">
              <h3 className="ce-section__title">AI assistant</h3>
              {!aiConfigured && aiSetupMessage && (
                <div className="ce-ai-setup" role="alert">
                  <strong>AI not connected yet</strong>
                  <pre className="ce-ai-setup__steps">{aiSetupMessage}</pre>
                </div>
              )}
              {aiConfigured && (
                <p className="ce-muted ce-section__hint">
                  Ask anything in plain English — answers use your real commission data
                  {explanation.ai?.provider ? ` (${explanation.ai.provider})` : ""}.
                  Local AI may take 30–60 seconds on the first question.
                </p>
              )}
              <div className="ce-chips">
                {suggestedQuestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="ce-chip"
                    onClick={() => setQuestion(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
              <form className="ce-ask-form" onSubmit={askQuestion}>
                <input
                  className="input ce-ask-input"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask the AI anything about this commission…"
                />
                <button
                  type="submit"
                  className="btn-secondary"
                  disabled={asking || !aiConfigured}
                >
                  {asking ? "Thinking… (may take up to a minute)" : "Ask AI"}
                </button>
              </form>
              {answer && answerSource !== "offline" && (
                <div className="ce-answer">
                  {answerSource === "ai" && (
                    <span className="ce-answer__badge">AI</span>
                  )}
                  {answerSource === "offline" && (
                    <span className="ce-answer__badge ce-answer__badge--muted">
                      Setup required
                    </span>
                  )}
                  <div className="ce-answer__text">{answer}</div>
                </div>
              )}
            </section>

            <section className="ce-section ce-section--whatif">
              <h3 className="ce-section__title">What-if simulator</h3>
              <p className="ce-muted ce-section__hint">
                If I sell more this period, what will my commission be?
              </p>
              <form className="ce-whatif-form" onSubmit={runWhatIf}>
                <label className="ce-whatif-label">
                  Extra sales ({explanation?.currency || "order currency"})
                  <input
                    type="number"
                    className="input"
                    min="1"
                    value={whatIfAmount}
                    onChange={(e) => setWhatIfAmount(e.target.value)}
                  />
                </label>
                <button type="submit" className="btn-secondary" disabled={simulating}>
                  {simulating ? "Calculating…" : "Simulate"}
                </button>
              </form>
              {whatIfResult?.error && (
                <p className="ce-error">{whatIfResult.error}</p>
              )}
              {whatIfResult?.summary && !whatIfResult.error && (
                <div className="ce-whatif-result">
                  <p>{whatIfResult.summary}</p>
                  <div className="ce-whatif-stats">
                    <span>
                      Additional: {formatMoney(
                        whatIfResult.projected_commission,
                        whatIfResult.currency || explanation?.currency
                      )}
                    </span>
                    <span>
                      Period total: {formatMoney(
                        whatIfResult.projected_total_commission,
                        whatIfResult.currency || explanation?.currency
                      )}
                    </span>
                  </div>
                </div>
              )}
            </section>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default CommissionExplanationModal;
