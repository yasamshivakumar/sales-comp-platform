import { useState } from "react";
import api from "../api";
import { useToast } from "./Toast";

function ChangePassword({ onClose }) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { success, error } = useToast();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!oldPassword || !newPassword || !confirmPassword) {
      error("All fields are required");
      return;
    }

    if (newPassword !== confirmPassword) {
      error("New passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      error("Password must be at least 8 characters long");
      return;
    }

    if (oldPassword === newPassword) {
      error("New password must be different from old password");
      return;
    }

    setLoading(true);
    try {
      await api.post("change-password/", {
        old_password: oldPassword,
        new_password: newPassword,
      });

      success("Password changed successfully! Please login again.");
      setTimeout(() => {
        localStorage.clear();
        window.location.href = "/login";
      }, 1500);
    } catch (err) {
      error(err.response?.data?.error || "Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose} role="presentation">
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="change-password-title"
      >
        <h2 id="change-password-title" className="modal-card__title">
          Change password
        </h2>

        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="old_password">Current password</label>
            <input
              id="old_password"
              type="password"
              placeholder="Enter current password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-field">
            <label htmlFor="new_password">New password</label>
            <input
              id="new_password"
              type="password"
              placeholder="At least 8 characters"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="form-field">
            <label htmlFor="confirm_password">Confirm new password</label>
            <input
              id="confirm_password"
              type="password"
              placeholder="Confirm new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              disabled={loading}
            />
          </div>

          <div className="modal-card__actions">
            <button
              type="submit"
              className="btn-success"
              style={{ flex: 1 }}
              disabled={loading}
            >
              {loading ? "Updating…" : "Update password"}
            </button>
            <button
              type="button"
              className="btn-secondary"
              style={{ flex: 1 }}
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default ChangePassword;
