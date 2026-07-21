import { useCallback, useEffect, useState } from "react";
import api, { clearAuthStorage } from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";

import UserSection from "./components/UserSection";
import PeopleSection from "./components/PeopleSection";
import TitleSection from "./components/TitleSection";
import PositionSection from "./components/PositionSection";
import HierarchySection from "./components/HierarchySection";
import BulkUploadSection from "./components/BulkUploadSection";
import { CURRENCY_OPTIONS } from "../utils/currency";
import { BUSINESS_GROUP_OPTIONS, currencyForBusinessGroup } from "../utils/businessGroups";

const INITIAL_FORM = {
  enable_login: true,
  name: "",
  email: "",
  role: "",
  username: "",
  first_name: "",
  last_name: "",
  prefix: "",
  employee_id: "",
  personal_target: "",
  personal_currency: "INR",
  business_group: "India",
  territory: "",
  region: "",
  title: "",
  pay_period_type: "Monthly",
  position_name: "",
  position_title: "",
  parent_participant: "",
  child_participant: "",
  split_percentage: "100",
};

const TABS = [
  { id: "User", label: "User", icon: "👤" },
  { id: "People", label: "People", icon: "🪪" },
  { id: "Title", label: "Title", icon: "💼" },
  { id: "Position", label: "Position", icon: "📍" },
  { id: "Hierarchy", label: "Hierarchy", icon: "🔗" },
  { id: "Upload", label: "Upload", icon: "📤" },
];

function UserSetup() {
  const [users, setUsers] = useState([]);
  const [file, setFile] = useState(null);
  const [activeTab, setActiveTab] = useState("User");
  const [form, setForm] = useState(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const { success, error, warning } = useToast();

  const fetchUsers = useCallback(() => {
    api
      .get("user-setup/")
      .then((res) => setUsers(res.data))
      .catch(() => error("Failed to load users"));
  }, [error]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const nextValue = type === "checkbox" ? checked : value;
    if (name === "business_group") {
      const groupCurrency = currencyForBusinessGroup(value, "");
      setForm({
        ...form,
        business_group: value,
        personal_currency: groupCurrency || form.personal_currency,
      });
      return;
    }
    setForm({ ...form, [name]: nextValue });
  };

  const renderField = (name, label, type = "text", placeholder = "") => (
    <div className="form-field">
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        type={type}
        name={name}
        value={form[name] ?? ""}
        onChange={handleChange}
        placeholder={placeholder || undefined}
      />
    </div>
  );

  const renderSelect = (name, label, options) => (
    <div className="form-field">
      <label htmlFor={name}>{label}</label>
      <select id={name} name={name} value={form[name] ?? ""} onChange={handleChange}>
        {options.map((opt) =>
          typeof opt === "object" ? (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ) : (
            <option key={opt} value={opt}>
              {opt}
            </option>
          )
        )}
      </select>
    </div>
  );

  const createUser = async () => {
    if (!form.email?.trim()) {
      warning("Email is required");
      return;
    }
    if (!form.role?.trim()) {
      warning("Role is required");
      return;
    }
    if (!form.employee_id?.trim()) {
      warning("Employee ID is required");
      return;
    }
    if (!form.name?.trim()) {
      warning("Name is required");
      return;
    }

    const emailKey = form.email.trim().toLowerCase();
    const empKey = form.employee_id.trim().toLowerCase();
    const dupEmail = users.find(
      (u) => (u.email || "").trim().toLowerCase() === emailKey
    );
    if (dupEmail) {
      warning(
        `Email already exists (${dupEmail.name || dupEmail.employee_id || dupEmail.email}).`
      );
      return;
    }
    const dupEmp = users.find(
      (u) => (u.employee_id || "").trim().toLowerCase() === empKey
    );
    if (dupEmp) {
      warning(
        `Employee ID already exists (${dupEmp.name || dupEmp.email || dupEmp.employee_id}).`
      );
      return;
    }

    setSaving(true);
    try {
      const payload = { ...form };
      const territoryText = String(payload.territory || "").trim();
      if (!territoryText) {
        delete payload.territory;
      } else {
        payload.territory = territoryText;
      }
      // Backend stores region on UserProfile.market
      payload.market = String(payload.region || payload.market || "").trim();
      delete payload.region;
      const res = await api.post("user-setup/", payload);

      if (form.parent_participant && form.child_participant && form.split_percentage) {
        await api.post("hierarchy-relationships/", {
          parent_participant: form.parent_participant,
          child_participant: form.child_participant,
          split_percentage: form.split_percentage,
        });
      }

      if (res.data?.invite_status === "sent") {
        success("Participant created and invite email sent");
      } else if (res.data?.invite_status === "created") {
        const inviteLink = res.data?.invite_link;
        const inviteError = res.data?.invite_error;
        const reason = inviteError ? ` Reason: ${inviteError}` : "";
        if (inviteLink) {
          navigator.clipboard?.writeText(inviteLink).catch(() => {});
          warning(
            `Participant created, but invite email could not be sent.${reason} Invite link copied: ${inviteLink}`
          );
        } else {
          warning(`Participant created. Invite email could not be sent.${reason} Check email settings.`);
        }
      } else {
        success("Participant created without login access. Enable login to send an invite.");
      }
      setForm(INITIAL_FORM);
      fetchUsers();
    } catch (err) {
      error(err.response?.data?.error || "Failed to save participant");
    } finally {
      setSaving(false);
    }
  };

  const uploadUsers = async () => {
    if (!file) {
      warning("Please select a CSV or Excel file");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      warning("CSV imports are limited to 10 MB. Split the file and retry.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api.post("user-setup-upload/", formData);
      if (res.status === 202 || res.data?.job_id) {
        success(
          `Upload queued — ${res.data?.row_count || "many"} users will import in the background.`
        );
        setFile(null);
        return;
      }
      const {
        success: ok = 0,
        failed = 0,
        errors = [],
        users_created: usersCreated = 0,
        users_updated: usersUpdated = 0,
        activation_emails_sent: emailsSent = 0,
        email_failures: emailFailures = 0,
      } = res.data || {};
      if (failed > 0) {
        const detail = errors
          .slice(0, 3)
          .map((e) => `Row ${e.row}: ${e.error}`)
          .join(" ");
        warning(
          `Upload finished — ${ok} succeeded, ${failed} failed.${detail ? ` ${detail}` : ""}`
        );
      } else {
        const parts = [
          `${usersCreated || ok} created`,
          usersUpdated ? `${usersUpdated} updated` : null,
          emailsSent ? `${emailsSent} activation email${emailsSent === 1 ? "" : "s"} sent` : null,
          emailFailures
            ? `${emailFailures} email failure${emailFailures === 1 ? "" : "s"}`
            : null,
        ].filter(Boolean);
        success(`Upload done — ${parts.join(" · ")}`);
      }
      if (ok > 0) fetchUsers();
      setFile(null);
    } catch (err) {
      if (err.response?.status === 401) {
        error("Session expired. Please log in again.");
        clearAuthStorage();
        window.location.href = "/login";
        return;
      }
      error(err.response?.data?.error || "Upload failed");
    }
  };

  const renderActiveTab = () => {
    const props = { form, handleChange, renderField, renderSelect, users };

    switch (activeTab) {
      case "User":
        return <UserSection {...props} />;
      case "People":
        return (
          <PeopleSection
            {...props}
            renderSelect={(name, label) => renderSelect(name, label, CURRENCY_OPTIONS)}
            renderBusinessGroupSelect={() =>
              renderSelect(
                "business_group",
                "Business group",
                BUSINESS_GROUP_OPTIONS.map((option) => ({
                  value: option.value,
                  label: `${option.label} (${option.currency})`,
                }))
              )
            }
          />
        );
      case "Title":
        return <TitleSection {...props} />;
      case "Position":
        return <PositionSection {...props} />;
      case "Hierarchy":
        return <HierarchySection {...props} />;
      case "Upload":
        return <BulkUploadSection file={file} setFile={setFile} uploadUsers={uploadUsers} />;
      default:
        return null;
    }
  };

  return (
    <div>
      <PageHeader
        badge="Administration"
        title="User Setup"
      />

      <div className="tabs setup-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab${activeTab === tab.id ? " tab--active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      <div className="panel">
        {renderActiveTab()}

        {activeTab !== "Upload" && (
          <div className="setup-panel__footer">
            <button type="button" className="btn-primary" onClick={createUser} disabled={saving}>
              {saving ? "Saving…" : "Save participant"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default UserSetup;
