import { useCallback, useEffect, useState } from "react";
import api, { getApiErrorMessage } from "../api";
import ChangePassword from "../Components/ChangePassword";
import PageChrome, { ChromeButton } from "../Components/layout/PageChrome";
import { useToast } from "../Components/Toast";
import "./profile.css";

const TIMEZONES = [
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Singapore",
  "Europe/London",
  "America/New_York",
  "America/Los_Angeles",
  "UTC",
];

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
];

function Section({ id, title, children, action }) {
  return (
    <section className="mp-section" id={id}>
      <div className="mp-section__head">
        <h2>{title}</h2>
        {action || null}
      </div>
      {children}
    </section>
  );
}

function MyProfile({ focus = "profile" }) {
  const { success, error } = useToast();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [form, setForm] = useState({
    name: "",
    first_name: "",
    last_name: "",
    phone: "",
    timezone: "Asia/Kolkata",
    language: "en",
    notification_preferences: {
      email_commissions: true,
      email_approvals: true,
      email_payouts: true,
      email_product: false,
    },
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, sRes] = await Promise.all([
        api.get("user-profile/"),
        api.get("auth/sessions/").catch(() => ({ data: { results: [] } })),
      ]);
      const p = pRes.data || {};
      setProfile(p);
      setForm({
        name: p.name || "",
        first_name: p.first_name || "",
        last_name: p.last_name || "",
        phone: p.phone || "",
        timezone: p.timezone || "Asia/Kolkata",
        language: p.language || "en",
        notification_preferences: p.notification_preferences || {
          email_commissions: true,
          email_approvals: true,
          email_payouts: true,
          email_product: false,
        },
      });
      setSessions(sRes.data?.results || []);
    } catch (err) {
      error({
        title: "Unable to load profile",
        message: getApiErrorMessage(err, "Try again."),
      });
    } finally {
      setLoading(false);
    }
  }, [error]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (focus === "preferences") {
      const el = document.getElementById("preferences");
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [focus, loading]);

  const savePersonal = async () => {
    if (!form.name.trim()) {
      error({ title: "Name required", message: "Enter a display name." });
      return;
    }
    setSaving(true);
    try {
      const res = await api.patch("user-profile/", {
        name: form.name.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone: form.phone.trim(),
      });
      setProfile(res.data);
      sessionStorage.setItem("name", res.data.name || "");
      success({ title: "Profile saved", message: "Your personal information was updated." });
    } catch (err) {
      error({
        title: "Save failed",
        message: getApiErrorMessage(err, "Could not update profile."),
      });
    } finally {
      setSaving(false);
    }
  };

  const savePreferences = async () => {
    setSaving(true);
    try {
      const res = await api.patch("user-profile/", {
        timezone: form.timezone,
        language: form.language,
        notification_preferences: form.notification_preferences,
      });
      setProfile(res.data);
      success({ title: "Preferences saved", message: "Your preferences were updated." });
    } catch (err) {
      error({
        title: "Save failed",
        message: getApiErrorMessage(err, "Could not update preferences."),
      });
    } finally {
      setSaving(false);
    }
  };

  const revokeSessions = async () => {
    if (!window.confirm("Sign out all other sessions? You will need to sign in again on other devices.")) {
      return;
    }
    try {
      await api.post("auth/sessions/revoke-all/");
      success({ title: "Sessions revoked", message: "Other sessions were signed out." });
      load();
    } catch (err) {
      error({
        title: "Unable to revoke",
        message: getApiErrorMessage(err, "Try again."),
      });
    }
  };

  const setNotif = (key, value) => {
    setForm((f) => ({
      ...f,
      notification_preferences: { ...f.notification_preferences, [key]: value },
    }));
  };

  if (loading) {
    return <p className="mp-muted">Loading profile…</p>;
  }

  return (
    <>
      <PageChrome
        eyebrow="Account"
        title="My Profile"
        subtitle="Manage your personal account — name, security, preferences, and sessions."
        primaryAction={
          <ChromeButton variant="primary" onClick={savePersonal} disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </ChromeButton>
        }
      >
        <nav className="mp-toc" aria-label="Profile sections">
          <a href="#personal">Personal</a>
          <a href="#security">Security</a>
          <a href="#preferences">Preferences</a>
          <a href="#sessions">Sessions</a>
        </nav>

        <Section id="personal" title="Personal information">
          <div className="mp-grid">
            <label>
              Display name
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </label>
            <label>
              First name
              <input
                value={form.first_name}
                onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
              />
            </label>
            <label>
              Last name
              <input
                value={form.last_name}
                onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
              />
            </label>
            <label>
              Phone
              <input
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                placeholder="+91…"
              />
            </label>
            <label>
              Email
              <input value={profile?.email || ""} disabled />
            </label>
            <label>
              Role
              <input value={profile?.role || ""} disabled />
            </label>
            <label>
              Employee ID
              <input value={profile?.employee_id || "—"} disabled />
            </label>
            <label>
              Organization
              <input value={profile?.organization_name || "—"} disabled />
            </label>
          </div>
          <p className="mp-hint">
            Email, role, and employee ID are managed by your administrator in People &amp; Access.
          </p>
        </Section>

        <Section id="picture" title="Profile picture">
          <div className="mp-avatar-block">
            <div className="mp-avatar" aria-hidden>
              {(profile?.name || profile?.email || "U")
                .split(/\s+/)
                .filter(Boolean)
                .slice(0, 2)
                .map((p) => p[0])
                .join("")
                .toUpperCase()}
            </div>
            <p className="mp-muted">
              Avatar initials are derived from your display name. Photo upload will be available in a
              later release.
            </p>
          </div>
        </Section>

        <Section
          id="security"
          title="Password & MFA"
          action={
            <ChromeButton onClick={() => setPasswordOpen(true)}>Change password</ChromeButton>
          }
        >
          <div className="mp-security">
            <div>
              <strong>Password</strong>
              <p className="mp-muted">Use a unique password for your Incentra account.</p>
            </div>
            <div>
              <strong>Multi-factor authentication</strong>
              <p className="mp-muted">
                Status: {profile?.mfa_enabled ? "Enabled" : "Not enabled"}
                {profile?.mfa_enabled
                  ? ""
                  : " — MFA enrollment is available when your organization requires it."}
              </p>
            </div>
          </div>
        </Section>

        <Section
          id="preferences"
          title="Preferences"
          action={
            <ChromeButton variant="primary" onClick={savePreferences} disabled={saving}>
              Save preferences
            </ChromeButton>
          }
        >
          <div className="mp-grid">
            <label>
              Time zone
              <select
                value={form.timezone}
                onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Language
              <select
                value={form.language}
                onChange={(e) => setForm((f) => ({ ...f, language: e.target.value }))}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <h3 className="mp-subhead">Notification preferences</h3>
          <div className="mp-checks">
            {[
              ["email_commissions", "Commission calculation emails"],
              ["email_approvals", "Approval workflow emails"],
              ["email_payouts", "Payout notifications"],
              ["email_product", "Product updates"],
            ].map(([key, label]) => (
              <label key={key} className="mp-check">
                <input
                  type="checkbox"
                  checked={Boolean(form.notification_preferences?.[key])}
                  onChange={(e) => setNotif(key, e.target.checked)}
                />
                {label}
              </label>
            ))}
          </div>
        </Section>

        <Section
          id="sessions"
          title="Active sessions"
          action={<ChromeButton onClick={revokeSessions}>Revoke all</ChromeButton>}
        >
          {!sessions.length ? (
            <p className="mp-muted">No session history available.</p>
          ) : (
            <div className="mp-table-wrap">
              <table className="mp-table">
                <thead>
                  <tr>
                    <th>IP</th>
                    <th>Device</th>
                    <th>Last seen</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.slice(0, 10).map((s) => (
                    <tr key={s.id}>
                      <td>{s.ip_address || "—"}</td>
                      <td className="mp-ua">{s.user_agent || s.device_id || "—"}</td>
                      <td>
                        {s.last_seen_at
                          ? new Date(s.last_seen_at).toLocaleString()
                          : "—"}
                      </td>
                      <td>{s.active ? "Active" : "Revoked"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section id="tokens" title="API tokens">
          <p className="mp-muted">
            Personal API tokens are not enabled for your role. Ask an administrator if your
            organization needs API access.
          </p>
        </Section>
      </PageChrome>

      {passwordOpen ? <ChangePassword onClose={() => setPasswordOpen(false)} /> : null}
    </>
  );
}

export default MyProfile;
