import { useEffect, useState } from "react";
import api from "../api";
import { useToast } from "../Components/Toast";
import PageHeader from "../Components/PageHeader";

import UserSection from "./components/UserSection";
import PeopleSection from "./components/PeopleSection";
import TitleSection from "./components/TitleSection";
import PositionSection from "./components/PositionSection";
import HierarchySection from "./components/HierarchySection";
import BulkUploadSection from "./components/BulkUploadSection";

const INITIAL_FORM = {
  enable_login: false,
  name: "",
  email: "",
  role: "Sales Rep",
  username: "",
  first_name: "",
  last_name: "",
  prefix: "",
  employee_id: "",
  personal_target: "",
  personal_currency: "INR",
  business_group: "India",
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

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = () => {
    api.get("user-setup/").then((res) => setUsers(res.data)).catch(() => {});
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm({ ...form, [name]: type === "checkbox" ? checked : value });
  };

  const renderField = (name, label, type = "text") => (
    <div className="form-field">
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        type={type}
        name={name}
        value={form[name] ?? ""}
        onChange={handleChange}
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

    setSaving(true);
    try {
      await api.post("user-setup/", form);

      if (form.parent_participant && form.child_participant && form.split_percentage) {
        await api.post("hierarchy-relationships/", {
          parent_participant: form.parent_participant,
          child_participant: form.child_participant,
          split_percentage: form.split_percentage,
        });
      }

      success("Participant saved successfully");
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

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await api.post("user-setup-upload/", formData);
      success(`Upload done — ${res.data.success} succeeded, ${res.data.failed} failed`);
      fetchUsers();
      setFile(null);
    } catch (err) {
      if (err.response?.status === 401) {
        error("Session expired. Please log in again.");
        localStorage.removeItem("token");
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
        return <PeopleSection {...props} />;
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
        // subtitle="Configure participants, positions, hierarchy, and bulk-import your sales team."
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
