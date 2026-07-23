import { useOutletContext } from "react-router-dom";
import { VersionBadge } from "../PlanVersionHistory";

const FLOW = ["Draft", "Published", "Archived"];

function ApprovalWorkflowTab() {
  const { plan } = useOutletContext();
  const versions = plan.versions_count ?? 0;
  const cv = plan.current_version;
  const status = cv?.status || "Draft";

  return (
    <div className="cp-tab">
      <section className="panel cp-tab-panel">
        <h2 className="panel__title">Approval workflow</h2>
        <p className="cp-tab-lead">
          Plan configuration follows the version lifecycle. Commission payout approvals
          remain in the Commissions module.
        </p>

        <ol className="cp-flow">
          {FLOW.map((step, idx) => {
            const active =
              status === step ||
              (step === "Published" && status === "Published") ||
              (FLOW.indexOf(status) >= idx && status !== "Draft");
            const current = status === step;
            return (
              <li
                key={step}
                className={`cp-flow__step${current ? " cp-flow__step--current" : ""}${
                  active ? " cp-flow__step--done" : ""
                }`}
              >
                <span className="cp-flow__dot" />
                <div>
                  <strong>{step}</strong>
                  {current ? <VersionBadge status={status} /> : null}
                  <p className="cp-tab-lead">
                    {step === "Draft" && "Editable rates, rules, and quotas."}
                    {step === "Published" && "Live for calculation; clone to edit."}
                    {step === "Archived" && "Retired from active use."}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>

        <div className="cp-overview-grid" style={{ marginTop: 16 }}>
          <div>
            <span className="cp-card__label">Current version</span>
            <span className="cp-card__value">
              {cv ? `v${cv.version_number}` : "—"} {cv ? <VersionBadge status={cv.status} /> : null}
            </span>
          </div>
          <div>
            <span className="cp-card__label">Versions on plan</span>
            <span className="cp-card__value">{versions}</span>
          </div>
          <div>
            <span className="cp-card__label">Last published by</span>
            <span className="cp-card__value">{plan.last_published_by || "—"}</span>
          </div>
        </div>
      </section>
    </div>
  );
}

export default ApprovalWorkflowTab;
