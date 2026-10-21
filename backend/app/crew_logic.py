"""
CrewAI multi-agent market analysis crew (Groq / Llama backend).

Agents:
  1. Market Researcher   — gathers live market data using web search.
  2. Business Strategist — synthesizes findings into a consultant-grade report.
"""

import logging

from crewai import Agent, Crew, LLM, Process, Task
from crewai_tools import SerperDevTool

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

llm = LLM(
    model=settings.groq_model_name,
    api_key=settings.groq_api_key,
    temperature=0.3,
    max_tokens=4096,
)

search_tool = SerperDevTool()


def build_market_researcher() -> Agent:
    return Agent(
        role="Senior Market Research Analyst",
        goal=(
            "Produce a rigorous, data-backed research brief on the given market topic. "
            "Identify market size, growth rate, key players, customer segments, "
            "pricing trends, and regulatory factors using live web sources. "
            "Always lead with the single most surprising or counterintuitive insight first."
        ),
        backstory=(
            "You are a senior analyst at a top-tier market intelligence firm with "
            "10+ years of experience in TAM/SAM/SOM sizing, competitor teardowns, "
            "and trend analysis. You never speculate — every claim is grounded in "
            "sources found via web search, and you cite the source URL next to each "
            "key data point. You distinguish between primary data (industry reports, "
            "earnings calls, job postings) and secondary data (news articles, blogs) "
            "and label each accordingly. For every market size claim you find at least "
            "two corroborating sources. You always search for recent funding rounds and "
            "M&A activity because they signal where smart money sees opportunity. "
            "You also find 2-3 recent customer reviews or community discussions "
            "(Reddit, G2, Capterra, LinkedIn) to surface real pain points."
        ),
        tools=[search_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=10,
    )


def build_business_strategist() -> Agent:
    return Agent(
        role="Chief Business Strategist",
        goal=(
            "Transform raw market research into a decision-ready strategic report. "
            "Your executive summary always opens with a single bold claim of the form: "
            "'[Founder/company] pursuing [market] should [specific action] because [quantified reason].' "
            "You never use passive voice. Every recommendation is specific and actionable."
        ),
        backstory=(
            "You are a former McKinsey partner turned fractional CBO for high-growth startups. "
            "You are known for turning noisy research into crisp, prioritized strategic narratives "
            "that founders and boards act on immediately. You write in clear, confident business "
            "English with zero fluff. Your risk registers always include a 'Who Owns This' column. "
            "You score every GTM channel by Reach, Cost, and Speed-to-first-revenue on a 1-5 scale. "
            "You always include a Quick Wins section — 3 actions doable in 30 days with zero budget."
        ),
        tools=[],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=6,
    )


def run_market_analysis_crew(market_topic: str) -> str:
    """Execute the two-agent crew and return the final markdown report."""
    researcher = build_market_researcher()
    strategist = build_business_strategist()

    research_task = Task(
        description=(
            f"Research the market for: '{market_topic}'.\n\n"
            "Deliver a structured research brief containing:\n"
            "1. **Surprising Insight First** — the single most counterintuitive finding about this market\n"
            "2. Market overview and TAM/SAM/SOM estimates with cited figures (two sources minimum per claim)\n"
            "3. Growth drivers and headwinds (with source links)\n"
            "4. Recent funding rounds and M&A activity — who is investing and why\n"
            "5. Top 5-7 competitors with positioning, pricing, and known weaknesses\n"
            "6. Customer segments and willingness-to-pay signals\n"
            "7. Real customer pain points from reviews/communities (Reddit, G2, Capterra, LinkedIn)\n"
            "8. Notable regulatory or technology shifts affecting the market\n\n"
            "Label each data point as [PRIMARY] or [SECONDARY] based on source type. "
            "Flag any data you could not verify as [UNVERIFIED]."
        ),
        expected_output=(
            "A markdown research brief of 700-1000 words with inline source citations "
            "(URL in parentheses after each key figure). "
            "Each section clearly labeled. Primary vs secondary data labeled."
        ),
        agent=researcher,
    )

    strategy_task = Task(
        description=(
            f"Using the research brief on '{market_topic}', produce the final "
            "client-facing strategic report in markdown with these exact sections:\n\n"
            f"# Market Analysis Report: {market_topic}\n\n"
            "## 1. Executive Summary\n"
            "Open with ONE bold claim sentence: "
            "'[Founder/company] pursuing [market] should [specific action] because [quantified reason].' "
            "Then 3-4 sentences of context. No passive voice.\n\n"
            "## 2. Market Opportunity Score\n"
            "Score 1-10 with a one-paragraph justification covering: market size, growth rate, "
            "competitive intensity, and timing.\n\n"
            "## 3. Competitive Landscape\n"
            "Table format: Competitor | Positioning | Pricing | Key Weakness | Threat Level\n\n"
            "## 4. Customer Pain Points\n"
            "Top 3 unmet needs with evidence from real customer reviews/communities.\n\n"
            "## 5. Recommended Positioning\n"
            "One crisp positioning statement + the single most defensible differentiator.\n\n"
            "## 6. Go-To-Market Strategy\n"
            "Table: Channel | Reach (1-5) | Cost (1-5) | Speed to Revenue (1-5) | Recommended Action\n\n"
            "## 7. Risk Register\n"
            "Table: Risk | Likelihood (H/M/L) | Impact (H/M/L) | Who Owns This | Mitigation\n\n"
            "## 8. Quick Wins (30-Day Zero-Budget Actions)\n"
            "Exactly 3 specific actions a founder can take in the next 30 days with no budget "
            "to validate the opportunity or gain an early advantage.\n\n"
            "## 9. 90-Day Action Plan\n"
            "Week-by-week breakdown: Week 1-2, Week 3-4, Month 2, Month 3. "
            "Each item actionable and specific.\n\n"
            "Keep total report under 2,000 words. "
            "Only use figures from the research brief — never invent statistics."
        ),
        expected_output=(
            "A polished markdown strategic report matching the exact section structure above. "
            "Must include the bold opener sentence, all tables, Quick Wins section, and 90-day plan."
        ),
        agent=strategist,
        output_file=None,
    )

    crew = Crew(
        agents=[researcher, strategist],
        tasks=[research_task, strategy_task],
        process=Process.sequential,
        memory=True,
        verbose=True,
        planning=True,
    )

    logger.info("Kicking off market analysis crew for topic: %s", market_topic)
    result = crew.kickoff(inputs={"market_topic": market_topic})
    report: str = result.raw
    logger.info("Crew finished. Report length: %d chars", len(report))
    return report
