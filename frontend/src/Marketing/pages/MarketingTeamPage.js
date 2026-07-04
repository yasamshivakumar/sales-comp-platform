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
      <section className="marketing-page-hero">
        <div className="marketing-page-hero__inner">
          <p className="marketing-kicker">Teams · {team.label}</p>
          <h1>{team.title}</h1>
          <p className="marketing-page-hero__lead">{team.body}</p>
        </div>
      </section>

      <section className="marketing-section marketing-section--wash">
        <div className="marketing-tabs marketing-tabs--links" role="tablist" aria-label="Solutions by team">
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
        <div className="marketing-persona marketing-persona--split" role="tabpanel">
          <div className="marketing-persona__copy">
            <h3>{team.title}</h3>
            <p>{team.body}</p>
            <ul className="marketing-persona__bullets">
              {team.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          </div>
          <TeamPersonaVisual label={team.label} bullets={team.bullets} />
        </div>
      </section>

      <MarketingCta />
    </>
  );
}

export default MarketingTeamPage;
