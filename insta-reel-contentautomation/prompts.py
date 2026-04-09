SEARCH_PROMPT = """
You are generating Instagram research hashtags.

Creator niche: {creator_niche}
Primary niche: {niche}
Location: {location}

Return five research-ready hashtags that balance specificity, adjacency, and reach.
"""


STRATEGY_PROMPT = """
You are the lead Instagram strategist for a short-form content operation.

Use the niche research, creator context, and posting history below to propose one strong reel concept.

Market research:
{market_research}

Creator context:
{creator_context}

Recent history:
{history}

Review feedback:
{review_feedback}
"""


WRITER_PROMPT = """
You are writing a production-ready Instagram reel package.

Requirements:
- The spoken script should feel natural and high-retention.
- It must include clear hook, buildup, payoff, and CTA.
- The caption should be publish-ready.
- Provide clean hashtag groupings.
- Suggest AI B-roll moments only when they materially improve retention.

Strategy:
{strategy}

Review feedback:
{review_feedback}
"""


REVIEW_PROMPT = """
Review this Instagram reel package.

Approve only if:
- the hook is strong in the first seconds
- the structure is coherent
- the caption matches the spoken script
- hashtags are relevant
- B-roll guidance is usable

Draft:
{draft}
"""
