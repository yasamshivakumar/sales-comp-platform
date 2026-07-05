import { SOLUTIONS_BY_FUNCTION } from "../marketingData";
import { useMarketingNav } from "../marketingNavContext";
import MarketingCta from "./MarketingCta";

function MarketingTeamsIndex() {
  const { showTeam } = useMarketingNav();

  return (
    <>
      <section className="marketing-page-hero marketing-page-hero--rich marketing-page-hero--catalog-teams">
        <div className="marketing-page-hero__inner marketing-page-hero__inner--wide">
          <div className="marketing-hero-badges">
            <span className="marketing-hero-badge">4 team workflows</span>
            <span className="marketing-hero-badge marketing-hero-badge--soft">Role-based</span>
          </div>
          <p className="marketing-kicker">Teams</p>
          <h1>How each team uses Incentra</h1>
          <p className="marketing-page-hero__lead">
            Finance, compensation, RevOps, and sales each get a focused workflow inside the
            same platform. Pick your team to see what matters most.
          </p>
        </div>
      </section>

      <section className="marketing-section marketing-section--rich marketing-section--catalog-teams">
        <div className="marketing-section__head marketing-section__head--center">
          <p className="marketing-kicker">Browse</p>
          <h2>Choose your team</h2>
        </div>
        <div className="marketing-card-grid marketing-card-grid--teams">
          {SOLUTIONS_BY_FUNCTION.map((team) => (
            <button
              key={team.slug}
              type="button"
              className={`marketing-card-link marketing-card-link--solid marketing-card-link--rich marketing-card-link--team-${team.slug}`}
              onClick={() => showTeam(team.slug)}
            >
              <span className="marketing-card-link__label">{team.label}</span>
              <h3>{team.title}</h3>
              <p>{team.body}</p>
              <span className="marketing-card-link__arrow">View for {team.label} →</span>
            </button>
          ))}
        </div>
      </section>

      <MarketingCta />
    </>
  );
}

export default MarketingTeamsIndex;
