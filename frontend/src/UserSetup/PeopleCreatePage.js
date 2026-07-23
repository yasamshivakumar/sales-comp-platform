import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { getApiErrorMessage } from "../api";
import { useToast } from "../Components/Toast";
import PeopleSection from "./components/PeopleSection";
import TitleSection from "./components/TitleSection";
import PositionSection from "./components/PositionSection";
import HierarchySection from "./components/HierarchySection";
import { CURRENCY_OPTIONS } from "../utils/currency";
import { BUSINESS_GROUP_OPTIONS, currencyForBusinessGroup } from "../utils/businessGroups";

const INITIAL_FORM = {
  enable_login: true,
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
  territory: "",
  region: "",
  department: "",
  phone: "",
  commission_eligible: true,
  title: "",
  pay_period_type: "Monthly",
  position_name: "",
  position_title: "",
  parent_participant: "",
  child_participant: "",
  split_percentage: "100",
};

const STEPS = [
  { id: "basic", label: "Basic Information" },
  { id: "org", label: "Organization" },
  { id: "access", label: "Access" },
];

const ROLE_PERMS = {
  Admin: [
    "View Plans",
    "Manage Plans",
    "Approve Transactions",
    "View Commissions",
    "Export Reports",
    "Manage Users",
  ],
  Finance: ["View Plans", "Approve Transactions", "View Commissions", "Export Reports"],
  Manager: ["View Plans", "View Commissions", "Export Reports", "Approve Transactions"],
  "Sales Rep": ["View own incentive details"],
};

function StyledCheckbox({ id, name, checked, onChange, title, hint }) {
  return (
    <label
      className={`checkbox-field${checked ? " checkbox-field--enabled" : ""}`}
      htmlFor={id}
    >
      <input
        type="checkbox"
        id={id}
        name={name}
        checked={Boolean(checked)}
        onChange={onChange}
      />
      <span className="checkbox-field__box" aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path
            d="M13.5 4.5 6.5 11.5 3 8"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="checkbox-field__copy">
        <span className="checkbox-field__title">{title}</span>
        {hint ? <span className="checkbox-field__hint">{hint}</span> : null}
      </span>
    </label>
  );
}

function PeopleCreatePage() {
  const navigate = useNavigate();
  const { success, error, warning } = useToast();
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [step, setStep] = useState(0);

  const fetchUsers = useCallback(() => {
    api
      .get("user-setup/", { params: { page_size: 100 } })
      .then((res) => {
        const data = res.data;
        setUsers(Array.isArray(data) ? data : data?.results || []);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const nextValue = type === "checkbox" ? checked : value;
    if (name === "business_group") {
      const groupCurrency = currencyForBusinessGroup(value, "");
      setForm((prev) => ({
        ...prev,
        business_group: value,
        personal_currency: groupCurrency || prev.personal_currency,
      }));
      return;
    }
    setForm((prev) => ({ ...prev, [name]: nextValue }));
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
        autoComplete="off"
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

  const validateStep = (idx) => {
    if (idx === 0) {
      if (!form.name?.trim()) return "Display name is required";
      if (!form.email?.trim()) return "Email is required";
      if (!form.employee_id?.trim()) return "Employee ID is required";
    }
    if (idx === 2) {
      if (!form.role?.trim()) return "System role is required";
    }
    return null;
  };

  const goNext = () => {
    const msg = validateStep(step);
    if (msg) {
      warning(msg);
      return;
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const createUser = async () => {
    for (let i = 0; i < STEPS.length; i += 1) {
      const msg = validateStep(i);
      if (msg) {
        warning(msg);
        setStep(i);
        return;
      }
    }

    setSaving(true);
    try {
      const payload = {
        ...form,
        enable_login: Boolean(form.enable_login),
        commission_eligible: Boolean(form.commission_eligible),
      };
      const territoryText = String(payload.territory || "").trim();
      if (!territoryText) delete payload.territory;
      else payload.territory = territoryText;
      payload.market = String(payload.region || payload.market || "").trim();
      delete payload.region;
      // Hierarchy is created separately if both sides set
      const parentId = payload.parent_participant;
      const childId = payload.child_participant;
      const split = payload.split_percentage;
      delete payload.parent_participant;
      delete payload.child_participant;
      delete payload.split_percentage;

      const res = await api.post("user-setup/", payload);
      const createdId = res.data?.id;

      if (parentId && childId && split) {
        try {
          await api.post("hierarchy-relationships/", {
            parent_participant: parentId,
            child_participant: childId === "self" || childId === "" ? createdId : childId,
            split_percentage: split,
          });
        } catch {
          warning("Person created, but hierarchy link failed");
        }
      }

      const inviteStatus = res.data?.invite_status;
      if (inviteStatus === "sent") {
        success("Person created and invite email sent");
      } else if (inviteStatus === "created" || inviteStatus === "email_failed") {
        const inviteLink = res.data?.invite_link;
        if (inviteLink) {
          navigator.clipboard?.writeText(inviteLink).catch(() => {});
          warning("Created — invite email failed. Invite link copied to clipboard.");
        } else {
          warning(
            res.data?.invite_error ||
              "Created. Invite email could not be sent — resend from the profile."
          );
        }
      } else if (form.enable_login) {
        warning("Created with login enabled, but invite status was unclear. Check the profile.");
      } else {
        success("Person created without login access.");
      }

      if (createdId) {
        navigate(`/user-setup/${createdId}/overview`);
      } else {
        navigate("/user-setup");
      }
    } catch (err) {
      error(getApiErrorMessage(err, err.response?.data?.error || "Failed to save person"));
    } finally {
      setSaving(false);
    }
  };

  const perms = useMemo(() => ROLE_PERMS[form.role] || ROLE_PERMS["Sales Rep"], [form.role]);
  const props = { form, handleChange, renderField, renderSelect, users };

  return (
    <div className="pe-subpage pe-create">
      <Link className="cp-btn-ghost" to="/user-setup">
        ← People & Access
      </Link>
      <h1>Create Person</h1>
      <p className="pe-muted">Multi-step onboarding: identity → organization → access.</p>

      <ol className="pe-steps">
        {STEPS.map((s, idx) => (
          <li
            key={s.id}
            className={idx === step ? "is-active" : idx < step ? "is-done" : ""}
          >
            <button
              type="button"
              className="pe-steps__btn"
              onClick={() => {
                if (idx <= step) setStep(idx);
                else {
                  const msg = validateStep(step);
                  if (msg) warning(msg);
                  else setStep(idx);
                }
              }}
            >
              {s.label}
            </button>
          </li>
        ))}
      </ol>

      <div className="panel pe-create__panel">
        {step === 0 ? (
          <div className="form-grid">
            <p className="section-heading">Basic information</p>
            <StyledCheckbox
              id="enable_login"
              name="enable_login"
              checked={form.enable_login}
              onChange={handleChange}
              title="Enable login & send invitation"
              hint="Employee must open the invite link and set a password before signing in."
            />
            {renderField("name", "Display name *")}
            {renderField("email", "Email *", "email")}
            {renderField("employee_id", "Employee ID *")}
            {renderField("phone", "Phone")}
            {renderField("first_name", "First name")}
            {renderField("last_name", "Last name")}
          </div>
        ) : null}

        {step === 1 ? (
          <>
            <PeopleSection
              {...props}
              renderSelect={(name, label) => renderSelect(name, label, CURRENCY_OPTIONS)}
              renderBusinessGroupSelect={() =>
                renderSelect(
                  "business_group",
                  "Business unit",
                  BUSINESS_GROUP_OPTIONS.map((option) => ({
                    value: option.value,
                    label: `${option.label} (${option.currency})`,
                  }))
                )
              }
            />
            {renderField("department", "Department")}
            <TitleSection {...props} />
            <PositionSection {...props} />
            <HierarchySection {...props} />
          </>
        ) : null}

        {step === 2 ? (
          <div className="pe-step-block">
            <p className="section-heading">Access</p>
            {renderSelect("role", "System Role *", [
              "Admin",
              "Finance",
              "Manager",
              "Sales Rep",
            ])}
            <p className="pe-muted">
              {form.role === "Sales Rep"
                ? "Sales Reps only see their own incentive / commission details — not admin or org-wide access."
                : "Permissions are derived from the system role selected above."}
            </p>
            {form.enable_login ? (
              <p className="pe-muted">
                Login is enabled — an invitation will be sent on create.
              </p>
            ) : (
              <p className="pe-muted">
                Login is off — turn it on in Basic Information if this person should sign in.
              </p>
            )}
            <div className="pe-perm-preview">
              <h3>Permissions for {form.role || "role"}</h3>
              <ul className="pe-perm-list">
                {perms.map((p) => (
                  <li key={p} className="ok">
                    ✓ {p}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}

        <div className="setup-panel__footer pe-create__footer">
          {step > 0 ? (
            <button type="button" className="btn-secondary" onClick={() => setStep((s) => s - 1)}>
              Back
            </button>
          ) : (
            <span />
          )}
          {step < STEPS.length - 1 ? (
            <button type="button" className="btn-primary" onClick={goNext}>
              Continue
            </button>
          ) : (
            <button type="button" className="btn-primary" onClick={createUser} disabled={saving}>
              {saving
                ? "Saving…"
                : form.enable_login
                  ? "Create & Invite"
                  : "Create Person"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default PeopleCreatePage;
