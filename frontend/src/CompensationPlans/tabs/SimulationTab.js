import { useOutletContext } from "react-router-dom";
import { SimulateCommissionModal } from "../CompPlansDataGrid";
import { useState } from "react";

/**
 * Workspace Simulation tab — entry point for commission what-if testing
 */
function SimulationTab() {
  const { plan } = useOutletContext();
  const [open, setOpen] = useState(true);

  return (
    <div className="cp-tab-panel">
      <h2 className="cp-section-title">Commission Simulation</h2>
      <p className="cp-tab-lead">
        Test how commissions calculate for this plan before publishing changes.
      </p>
      <button type="button" className="btn-primary" onClick={() => setOpen(true)}>
        Simulate Commission
      </button>
      {open && plan ? (
        <SimulateCommissionModal plan={plan} onClose={() => setOpen(false)} />
      ) : null}
    </div>
  );
}

export default SimulationTab;
