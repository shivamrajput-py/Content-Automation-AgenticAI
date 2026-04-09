SEARCH_PLANNER_PROMPT = """
You are a social research planner.

Create a compact set of Instagram/Twitter/LinkedIn search terms for this creator:
- Creator niche: {creator_niche}
- Primary niche: {niche}
- Location: {location}
- Language: {language_of_text}

Return a balanced mix of:
1. Exact niche terms
2. Close variations
3. Broader adjacent trend terms

Keep the list highly actionable for scraping and do not include fluff.
"""


SYNTHESIS_PROMPT = """
You are the lead research strategist for a short-form content team.

Use the research payload below to produce a publication-grade strategic brief.
Focus on what will help a creator make better content decisions immediately.

Research payload:
{research_payload}
"""


QUALITY_REVIEW_PROMPT = """
Review this research brief for completeness and tactical usefulness.

Approve only if it includes:
- clear Instagram pattern analysis
- cross-platform trends from Twitter and LinkedIn
- concrete content recommendations
- no obvious contradictions

Brief:
{brief}
"""
