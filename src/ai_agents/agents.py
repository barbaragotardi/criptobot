"""Three agents + diagnostician. Prompts are pt-BR; outputs are schema-bound."""

from src.ai_agents.schemas import AssetDiagnosis, Briefing, NewsView, RiskView

NEWS_SYS = ("Você é um analista fundamentalista de cripto. Responda SOMENTE com JSON válido"
            " no schema dado. Nunca invente preços, percentuais ou números. Cite apenas os"
            " ids de evidência fornecidos. Sem notícias relevantes: sentiment neutral,"
            " confidence low, listas vazias.")

RISK_SYS = ("Você comenta risco de concentração a partir dos FATOS dados. Responda SOMENTE"
            " com JSON válido. Nunca invente números; use apenas os fatos. Máximo 5 notas curtas.")

CHIEF_SYS = ("Você sintetiza o briefing final em pt-BR. Responda SOMENTE com JSON válido."
             " bullets curtos, sem preços, sem percentuais, sem recomendação de compra."
             " Tom caution se houver risco alto ou notícia bearish com confiança alta.")

DIAG_SYS = ("Você narra o estado técnico a partir dos FATOS dados. Responda SOMENTE com JSON"
            " válido. Sem preços novos, sem recomendação.")


def run_news(conn, cfg, snippets: list[dict]) -> NewsView:
    from src.ai_agents.llm import complete_structured, strip_numbered
    if not snippets:
        return NewsView()
    lines = [f"[{s['id']}] {s['source']}: {s['title']} — {s['summary']}" for s in snippets]
    user = "Notícias:\n" + "\n".join(lines[:12])
    parsed, _ = complete_structured(conn, cfg, "news_analyst", NewsView, NEWS_SYS, user)
    known = {s["id"] for s in snippets} | {s["id"][:8] for s in snippets}
    v = parsed.validated({s["id"] for s in snippets} | known)
    return NewsView(sentiment=v.sentiment,
                    catalysts=strip_numbered(v.catalysts)[:5],
                    risks=strip_numbered(v.risks)[:5],
                    evidence_ids=v.evidence_ids, confidence=v.confidence)


def run_risk(conn, cfg, facts: str) -> RiskView:
    from src.ai_agents.llm import complete_structured, strip_numbered
    parsed, _ = complete_structured(conn, cfg, "risk_commentator", RiskView,
                                    RISK_SYS, f"FATOS:\n{facts}")
    return RiskView(concentration=parsed.concentration,
                    notes=strip_numbered(parsed.notes)[:5])


def run_chief(conn, cfg, news: NewsView, risk: RiskView, asset: str, state: str) -> Briefing:
    from src.ai_agents.llm import complete_structured, strip_numbered
    user = (f"Ativo {asset} estado {state}. News: {news.model_dump_json()}."
            f" Risk: {risk.model_dump_json()}. Gere o briefing.")
    parsed, _ = complete_structured(conn, cfg, "chief_advisor", Briefing, CHIEF_SYS, user)
    return Briefing(tone=parsed.tone, bullets=strip_numbered(parsed.bullets)[:6])


def run_diagnostician(conn, cfg, facts: str) -> AssetDiagnosis:
    from src.ai_agents.llm import complete_structured
    parsed, _ = complete_structured(conn, cfg, "diagnostician", AssetDiagnosis,
                                    DIAG_SYS, f"FATOS:\n{facts}")
    return parsed
