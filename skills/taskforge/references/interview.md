# Interview script

Keep it short and conversational — a few questions, not a form. The goal is enough to pick a good
slice and the right difficulty. Confirm your understanding before moving on.

Ask (adapt wording to the conversation):

1. **Role & signal.** "What role is this for, and what do you most want to learn about a candidate —
   debugging, code reading, API design, testing, working in unfamiliar code?"
2. **Difficulty / time.** "Target seniority (junior / mid / senior), and how long should it take —
   roughly 1–2 hours?" (You'll estimate solve-time yourself at the taskify gate; this sets the aim.)
3. **The source.** "Point me at a real GitHub issue or PR — a link is best." If they don't have one,
   offer to browse: `gh issue list` / `gh pr list --state merged`.
4. **Language/stack** — only if the repo is polyglot and it's ambiguous which part the issue touches.
5. **Who's building this.** "Whose name should I put on this task for your records?" (operator;
   optionally email / `gh` login). This goes in the trusted scorecard's `created_by`, never to the
   candidate.

Then **read it back**: "So: a {seniority} {language} task from issue #{n}, aiming ~{time}, built by
{operator}, testing {signal}. Good?" — get a yes before Phase 2.

Notes:
- Prefer issues/PRs about a **self-contained module** — easier to carve into a standalone project.
- Steer away from auth / crypto / payment topics early; the safety gate will refuse them anyway, so
  don't waste the user's time carving one.
