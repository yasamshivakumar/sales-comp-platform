import { useBookDemo } from "./useBookDemo";

function BookDemoForm() {
  const { demoForm, demoStatus, demoSubmitting, updateDemoForm, submitDemoRequest } = useBookDemo();

  return (
    <form className="marketing-demo-form" onSubmit={submitDemoRequest}>
      <label>
        <span>Full name *</span>
        <input
          value={demoForm.name}
          onChange={updateDemoForm("name")}
          placeholder="Jane Smith"
          required
        />
      </label>
      <label>
        <span>Work email *</span>
        <input
          type="email"
          value={demoForm.email}
          onChange={updateDemoForm("email")}
          placeholder="jane@company.com"
          required
        />
      </label>
      <label>
        <span>Company</span>
        <input
          value={demoForm.company}
          onChange={updateDemoForm("company")}
          placeholder="Company name"
        />
      </label>
      <label>
        <span>Phone</span>
        <input
          value={demoForm.phone}
          onChange={updateDemoForm("phone")}
          placeholder="+1 or +91 number"
        />
      </label>
      <label className="marketing-demo-form__full">
        <span>What do you want to see?</span>
        <textarea
          value={demoForm.message}
          onChange={updateDemoForm("message")}
          placeholder="e.g. lookup plans, HubSpot sync, hierarchy splits"
          rows={4}
        />
      </label>
      <label className="marketing-demo-form__honeypot" aria-hidden="true">
        <span>Website</span>
        <input
          tabIndex={-1}
          autoComplete="off"
          value={demoForm.website}
          onChange={updateDemoForm("website")}
        />
      </label>
      <button
        type="submit"
        className="marketing-btn marketing-btn--primary marketing-demo-form__submit"
        disabled={demoSubmitting}
      >
        {demoSubmitting ? "Submitting…" : "Submit request"}
      </button>
      {demoStatus.message && (
        <div className={`marketing-demo-form__status marketing-demo-form__status--${demoStatus.type}`}>
          <p>{demoStatus.message}</p>
          {demoStatus.type === "error" && (
            <div className="marketing-demo-form__fallback">
              <a href={`mailto:${demoStatus.email}`}>{demoStatus.email}</a>
              <a href={`tel:+91${demoStatus.phone}`}>{demoStatus.phone}</a>
            </div>
          )}
        </div>
      )}
    </form>
  );
}

export default BookDemoForm;
