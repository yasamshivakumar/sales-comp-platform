import { getTeamSolution, SOLUTIONS_BY_FUNCTION } from "../marketingData";
import { useMarketingNav } from "../marketingNavContext";
import { TeamPersonaVisual } from "../MarketingVisuals";
import MarketingCta from "./MarketingCta";

function MarketingTeamPage({ slug }) {
  const { showTeam } = useMarketingNav();
  const team = getTeamSolution(slug);

  if (!team) {
    return null;
  }

  return (
    <>
      <section className={`marketing-page-hero marketing-page-hero--rich marketing-page-hero--team-${slug}`}>
        <div className="marketing-page-hero__inner marketing-page-hero__inner--wide">
          <div className="marketing-hero-badges">
            <span className="marketing-hero-badge">Team workflow</span>
            <span className="marketing-hero-badge marketing-hero-badge--soft">{team.label}</span>
          </div>
          <p className="marketing-kicker">Teams · {team.label}</p>
          <h1>{team.title}</h1>
          <p className="marketing-page-hero__lead">{team.body}</p>
          <div className="marketing-capability-row">
            {team.bullets.map((bullet) => (
              <span key={bullet} className="marketing-capability-chip">
                {bullet}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className={`marketing-section marketing-section--rich marketing-section--team-${slug}`}>
        <div className="marketing-tabs marketing-tabs--rich marketing-tabs--links" role="tablist" aria-label="Solutions by team">
          {SOLUTIONS_BY_FUNCTION.map((item) => (
            <button
              key={item.slug}
              type="button"
              role="tab"
              aria-selected={item.slug === slug}
              className={`marketing-tabs__btn${item.slug === slug ? " marketing-tabs__btn--active" : ""}`}
              onClick={() => showTeam(item.slug)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="marketing-persona marketing-persona--rich marketing-persona--split" role="tabpanel">
          <div className="marketing-persona__copy">
            <span className="marketing-persona__eyebrow">Built for {team.label}</span>
            <h3>What {team.label} teams do in Incentra</h3>
            <div className="marketing-check-grid">
              {team.bullets.map((bullet) => (
                <div key={bullet} className="marketing-check-item">
                  <span className="marketing-check-item__mark" aria-hidden="true">
                    ✓
                  </span>
                  <span>{bullet}</span>
                </div>
              ))}
            </div>
          </div>
          <TeamPersonaVisual label={team.label} bullets={team.bullets} slug={slug} />
        </div>
      </section>

      <MarketingCta />
    </>
  );
}

export default MarketingTeamPage;
