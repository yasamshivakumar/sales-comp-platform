import { useEffect, useState } from "react";
import api from "../../api";

function HierarchySection({ form, handleChange, renderField }) {
  const [participants, setParticipants] = useState([]);
  const [participantSearch, setParticipantSearch] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const term = participantSearch.trim();
    const timer = window.setTimeout(() => {
      setLoading(true);
      const params = new URLSearchParams();
      if (term) {
        params.set("q", term);
      } else {
        params.set("limit", "15");
      }
      api
        .get(`user-setup/?${params.toString()}`)
        .then((res) => {
          if (!cancelled) setParticipants(res.data || []);
        })
        .catch(() => {
          if (!cancelled) setParticipants([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, term ? 300 : 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [participantSearch]);

  const userLabel = (user) => {
    const name = `${user.first_name || ""} ${user.last_name || ""}`.trim();
    return name || user.name || user.email || `User #${user.id}`;
  };

  const showBrowseHint = !participantSearch.trim() && participants.length >= 15;

  return (
    <div className="form-grid">
      <p className="section-heading">Reporting hierarchy</p>
      <p className="hierarchy-hint">
        Split percentage is the share the <strong>child (seller)</strong> keeps.
        The parent receives the remainder (e.g. 80 = rep keeps 80%, manager gets 20%).
      </p>

      <div className="form-field form-field--full">
        <label htmlFor="participant_search">Find participant</label>
        <input
          id="participant_search"
          type="search"
          value={participantSearch}
          onChange={(e) => setParticipantSearch(e.target.value)}
          placeholder="Search by name, email, or employee ID…"
          autoComplete="off"
        />
        {showBrowseHint && (
          <p className="hierarchy-hint">Showing 15 employees. Search to find others.</p>
        )}
        {loading && <p className="hierarchy-hint">Loading participants…</p>}
      </div>

      <div className="form-field">
        <label htmlFor="parent_participant">Parent (manager)</label>
        <select
          id="parent_participant"
          name="parent_participant"
          value={form.parent_participant}
          onChange={handleChange}
        >
          <option value="">Select parent participant</option>
          {participants.map((user) => (
            <option key={user.id} value={user.id}>
              {userLabel(user)}
            </option>
          ))}
        </select>
      </div>

      <div className="form-field">
        <label htmlFor="child_participant">Child (direct report)</label>
        <select
          id="child_participant"
          name="child_participant"
          value={form.child_participant}
          onChange={handleChange}
        >
          <option value="">Select child participant</option>
          {participants.map((user) => (
            <option key={user.id} value={user.id}>
              {userLabel(user)}
            </option>
          ))}
        </select>
      </div>

      {renderField("split_percentage", "Child retention %", "number")}
    </div>
  );
}

export default HierarchySection;
