import { Navigate, Route, Routes } from "react-router-dom";
import CompPlansCatalog from "./CompPlansCatalog";
import CompPlanWorkspace from "./CompPlanWorkspace";
import CompPlanCreatePage from "./CompPlanCreatePage";
import AiPlanBuilder from "./AiPlanBuilder";
import OverviewTab from "./tabs/OverviewTab";
import VersionsTab from "./tabs/VersionsTab";
import RatesTab from "./tabs/RatesTab";
import RulesTab from "./tabs/RulesTab";
import QuotasTab from "./tabs/QuotasTab";
import ParticipantsTab from "./tabs/ParticipantsTab";
import SettingsTab from "./tabs/SettingsTab";
import BonusesTab, { AcceleratorsTab } from "./tabs/BonusesTab";
import EligibilityTab from "./tabs/EligibilityTab";
import ApprovalWorkflowTab from "./tabs/ApprovalWorkflowTab";
import HistoryTab from "./tabs/HistoryTab";
import SimulationTab from "./tabs/SimulationTab";
import DocumentsTab from "./tabs/DocumentsTab";
import OverridesTab from "./tabs/OverridesTab";
import "./compPlans.css";

function CompensationPlans() {
  return (
    <Routes>
      <Route index element={<CompPlansCatalog />} />
      <Route path="new" element={<CompPlanCreatePage />} />
      <Route path="ai" element={<AiPlanBuilder />} />
      <Route path=":planId" element={<CompPlanWorkspace />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<OverviewTab />} />
        <Route path="versions" element={<VersionsTab />} />
        <Route path="rates" element={<RatesTab />} />
        <Route path="rules" element={<RulesTab />} />
        <Route path="quotas" element={<QuotasTab />} />
        <Route path="documents" element={<DocumentsTab />} />
        <Route path="bonuses" element={<BonusesTab />} />
        <Route path="accelerators" element={<AcceleratorsTab />} />
        <Route path="eligibility" element={<EligibilityTab />} />
        <Route path="participants" element={<ParticipantsTab />} />
        <Route path="overrides" element={<OverridesTab />} />
        <Route path="simulation" element={<SimulationTab />} />
        <Route path="approval" element={<ApprovalWorkflowTab />} />
        <Route path="history" element={<HistoryTab />} />
        <Route path="settings" element={<SettingsTab />} />
      </Route>
      <Route path="*" element={<Navigate to="." replace />} />
    </Routes>
  );
}

export default CompensationPlans;
