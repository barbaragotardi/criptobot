"""Three agents + diagnostician. Prompts are pt-BR; outputs are schema-bound."""

from src.ai_agents.schemas import AssetDiagnosis, Briefing, NewsView, RiskView

TOPICS = ("regulation, etf_flows, hack_exploit, macro_rates, exchange_listing,"
          " partnership, protocol_upgrade, liquidations, adoption, legal,"
          " whale_activity, other")

NEWS_SYS = ("Você é um analista fundamentalista de cripto. Responda SOMENTE com JSON válido"
            " no schema dado. sentiment: bullish|bearish|neutral. confidence: low|medium|high."
            " catalysts e risks aceitam SÓ estes códigos: " + TOPICS + "."
            " Cite apenas os ids de evidência fornecidos."
            " rationale: UMA frase curta, sem preços, sem percentuais, sem $, %, sem dígitos longos."
            " Sem notícias relevantes: sentiment neutral,"
            " confidence low, listas vazias.")

RISK_SYS = ("Você comenta risco de concentração a partir dos FATOS dados. Responda SOMENTE"
            " com JSON válido. concentration: high|medium|low. flags aceita SÓ estes códigos:"
            " many_open_positions, high_correlation, already_holding_paper,"
            " already_holding_manual, near_exposure_cap. Máximo 5 flags, sem texto livre.")

CHIEF_SYS = ("Você sintetiza o briefing final em pt-BR. Responda SOMENTE com JSON válido."
             " tone: supportive|neutral|caution. bullets: no máximo 6 frases curtas"
             " (cada uma até 140 caracteres), sem preços, sem percentuais, sem $, %,"
             " sem recomendação de compra."
             " Tom caution se houver risco alto ou notícia bearish com confiança alta.")

DIAG_SYS = ("Você classifica o estado técnico a partir dos FATOS dados. Responda SOMENTE com JSON"
            " válido. blockers aceita SÓ: market_bearish, macro_fail, no_pullback,"
            " cooldown_active, awaiting_confirmation, exposure_blocked, rr_below_min, tp_below_min."
            " watchers aceita SÓ: near_ema20, near_ema50, awaiting_confirmation, near_support."
            " Sem texto livre, sem números, sem recomendação.")


def _dedup(items: list[str], limit: int) -> list[str]:
    seen: list[str] = []
    for x in items or []:
        if x not in seen:
            seen.append(x)
        if len(seen) >= limit:
            break
    return seen


def run_news(conn, cfg, snippets: list[dict], _trace: dict | None = None) -> NewsView:
    from src.ai_agents.llm import complete_structured
    if not snippets:
        return NewsView()
    lines = [f"[{s['id']}] {s['source']}: {s['title']} — {s['summary']}" for s in snippets]
    user = "Notícias:\n" + "\n".join(lines[:12])
    parsed, _ = complete_structured(conn, cfg, "news_analyst", NewsView, NEWS_SYS, user,
                                    _trace=_trace)
    known = {s["id"] for s in snippets} | {s["id"][:8] for s in snippets}
    v = parsed.validated({s["id"] for s in snippets} | known)
    rationale = (v.rationale or "")[:140]
    return NewsView(sentiment=v.sentiment,
                    catalysts=_dedup(v.catalysts, 5),
                    risks=_dedup(v.risks, 5),
                    evidence_ids=v.evidence_ids, confidence=v.confidence,
                    rationale=rationale)


def run_risk(conn, cfg, facts: str, _trace: dict | None = None) -> RiskView:
    from src.ai_agents.llm import complete_structured
    parsed, _ = complete_structured(conn, cfg, "risk_commentator", RiskView,
                                    RISK_SYS, f"FATOS:\n{facts}", _trace=_trace)
    return RiskView(concentration=parsed.concentration,
                    flags=_dedup(parsed.flags, 5))


def run_chief(conn, cfg, news: NewsView, risk: RiskView, asset: str, state: str,
              _trace: dict | None = None) -> Briefing:
    from src.ai_agents.llm import complete_structured
    user = (f"Ativo {asset} estado {state}. News: {news.model_dump_json()}."
            f" Risk: {risk.model_dump_json()}. Gere o briefing.")
    parsed, _ = complete_structured(conn, cfg, "chief_advisor", Briefing, CHIEF_SYS, user,
                                    _trace=_trace)
    bullets = [b[:140] for b in (parsed.bullets or []) if b][:6]
    return Briefing(tone=parsed.tone, bullets=bullets)


def run_diagnostician(conn, cfg, facts: str, _trace: dict | None = None) -> AssetDiagnosis:
    from src.ai_agents.llm import complete_structured
    parsed, _ = complete_structured(conn, cfg, "diagnostician", AssetDiagnosis,
                                    DIAG_SYS, f"FATOS:\n{facts}", _trace=_trace)
    return AssetDiagnosis(blockers=_dedup(parsed.blockers, 5),
                          watchers=_dedup(parsed.watchers, 5))
