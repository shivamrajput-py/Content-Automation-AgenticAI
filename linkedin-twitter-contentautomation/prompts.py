SEARCH_PROMPT = """
You are building search queries for cross-platform social trend research.

Creator niche: {creator_niche}
Primary niche: {niche}
Location: {location}

Return search phrases that will surface the most current conversations on both LinkedIn and X.
Keep them concrete, high-signal, and non-duplicative.
"""


STRATEGY_PROMPT = """
You are the content strategy architect for a founder-brand social account.

Use the market research and recent posting history below to create a strong angle for one LinkedIn post
and one X post. Avoid repeating recently covered topics.

Research:
{research}

Recent history:
{history}

Feedback from review loop:
{review_feedback}
"""


WRITER_PROMPT = """
You are the execution writer.

Turn the approved strategy into:
1. A LinkedIn post that reads like thoughtful operator insight.
2. An X post that is concise and high-shareability.

Strategy:
{strategy}

Review feedback to address:
{review_feedback}
"""


REVIEW_PROMPT = """
Review the generated social copy.

Approve only if:
- the LinkedIn post feels substantive and natural
- the X post is punchy and under platform limits
- hashtags are relevant but not spammy
- both posts are clearly differentiated

Draft:
{draft}
"""


IMAGE_PROMPT = """
Create one professional AI image prompt for a LinkedIn post.

LinkedIn post:
{linkedin_post}

Strategy:
{strategy}
"""
