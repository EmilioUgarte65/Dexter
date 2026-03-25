#!/usr/bin/env python3
"""
Dexter — LinkedIn Content Generator.
Generates optimized post content, hashtags, and hooks. Copies to clipboard.
NO LinkedIn API calls — paste content manually to avoid ToS violations.

Usage:
  content.py draft <topic> [--tone professional|casual|storytelling] [--length short|medium|long]
  content.py hashtags <topic>
  content.py hook <topic>
"""

import sys
import os
import argparse
import subprocess
import textwrap
from typing import Optional

# ─── ANSI colors ──────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

# ─── Config ───────────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# ─── Clipboard helper ─────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard. Returns True on success."""
    cmds = [
        ["xclip", "-selection", "clipboard"],   # Linux (xclip)
        ["xsel", "--clipboard", "--input"],      # Linux (xsel)
        ["pbcopy"],                              # macOS
        ["clip.exe"],                            # Windows WSL
    ]
    for cmd in cmds:
        try:
            proc = subprocess.run(cmd, input=text.encode(), capture_output=True, timeout=5)
            if proc.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False


# ─── AI-enhanced generation (optional) ───────────────────────────────────────

def _openai_generate(prompt: str) -> Optional[str]:
    """Call OpenAI API if key is available."""
    if not OPENAI_API_KEY:
        return None
    try:
        import urllib.request
        import json
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 600,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


# ─── Templates ────────────────────────────────────────────────────────────────

HOOKS_TEMPLATES = [
    "I spent {X} years learning this, so you don't have to:",
    "Nobody talks about the hardest part of {topic}.",
    "3 years ago, I knew nothing about {topic}. Here's what changed everything:",
    "Hot take: most people approach {topic} completely wrong.",
    "The {topic} advice that actually worked for me (and why most tips are useless):",
]

HASHTAG_CATEGORIES = {
    "business":     ["#entrepreneurship", "#startup", "#business", "#leadership", "#innovation"],
    "tech":         ["#technology", "#software", "#programming", "#AI", "#machinelearning"],
    "career":       ["#career", "#jobsearch", "#hiring", "#worklife", "#professionaldevelopment"],
    "marketing":    ["#marketing", "#digitalmarketing", "#contentmarketing", "#socialmedia", "#growth"],
    "productivity": ["#productivity", "#timemanagement", "#focus", "#habits", "#mindset"],
    "default":      ["#linkedin", "#networking", "#learning", "#inspiration", "#success"],
}


def _generate_hashtags_template(topic: str) -> list[str]:
    topic_lower = topic.lower()
    tags = set()

    for category, htags in HASHTAG_CATEGORIES.items():
        keywords = {
            "business":     ["business", "startup", "company", "entrepreneur", "CEO"],
            "tech":         ["tech", "software", "code", "AI", "data", "machine", "developer"],
            "career":       ["career", "job", "work", "hiring", "interview", "salary"],
            "marketing":    ["marketing", "brand", "content", "social", "ads", "growth"],
            "productivity": ["productivity", "habit", "time", "focus", "morning", "routine"],
        }.get(category, [])

        if any(kw.lower() in topic_lower for kw in keywords):
            tags.update(htags)

    # Always add default
    tags.update(HASHTAG_CATEGORIES["default"][:3])

    # Add topic-specific
    words = [w.strip(".,!?") for w in topic.split() if len(w) > 4]
    for w in words[:3]:
        tags.add(f"#{w.capitalize()}")

    return sorted(tags)[:10]


def _draft_professional_short(topic: str) -> str:
    return f"""The key to {topic} comes down to 3 things:

1. Start with a clear outcome in mind
2. Measure what matters, ignore the rest
3. Iterate fast — perfection is the enemy of progress

What's your approach to {topic}?

Share your experience below. ⬇️"""


def _draft_professional_medium(topic: str) -> str:
    return f"""Most people overcomplicate {topic}.

Here's the framework that actually works:

→ Define success before you start
→ Build feedback loops early
→ Involve stakeholders at every step
→ Document decisions, not just outcomes

The organizations I've seen succeed with {topic} share one trait: they treat it as a continuous process, not a one-time project.

What's the biggest challenge you've faced with {topic}? Drop a comment — I read every one.

#ProfessionalDevelopment #Leadership"""


def _draft_professional_long(topic: str) -> str:
    return f"""I've spent years studying what separates high-performing teams from the rest when it comes to {topic}.

The answer isn't what most people expect.

It's not talent. It's not resources. It's not even strategy.

It's clarity of purpose combined with disciplined execution.

Here's what that looks like in practice:

PHASE 1 — Alignment
Before doing anything, every stakeholder must agree on the definition of success. Not a vague goal — a measurable outcome with a deadline.

PHASE 2 — Focused Execution
Limit work in progress. The teams I've seen deliver consistently pick 2-3 priorities and say no to everything else.

PHASE 3 — Learning Loops
Weekly retrospectives. Not to assign blame. To extract patterns. What worked? What didn't? What do we change?

PHASE 4 — Communication
Overcommunicate progress. Silence creates uncertainty. Uncertainty creates fear. Fear kills momentum.

I've applied this to {topic} across multiple organizations, and the results consistently improve when teams follow this structure.

What's missing from this framework? I'd love to hear your perspective.

#Leadership #Strategy #ProfessionalGrowth"""


def _draft_casual_short(topic: str) -> str:
    return f"""Real talk about {topic}:

✅ What works: keeping it simple
❌ What doesn't: trying to do everything at once
🔑 The secret: consistency > intensity

Anyone else feel this way? 👇"""


def _draft_casual_medium(topic: str) -> str:
    return f"""Hot take: {topic} doesn't have to be complicated.

I used to overthink it. Spent hours reading about the "right" approach.

Then I realized: the people actually getting results aren't reading about it. They're doing it.

Here's my no-BS take:
• Start before you're ready
• Learn from your mistakes faster than everyone else
• Don't wait for permission

That's it. That's the whole framework.

What's one thing about {topic} that clicked for you recently? 👇"""


def _draft_casual_long(topic: str) -> str:
    return f"""Okay let's talk about {topic} because I have feelings.

Three years ago I was completely lost. Tried everything. Read every book. Watched every YouTube video.

Nothing worked.

Then one day I had a conversation with someone who'd been doing this for 20 years and they said something I'll never forget:

"Stop trying to be perfect. Start trying to be consistent."

That changed everything.

I stopped trying to optimize every detail. I stopped comparing myself to people 10 steps ahead of me. I just... showed up. Every day.

Month 1: Felt like nothing was happening
Month 3: Starting to see small wins
Month 6: People started asking for advice

The irony of {topic} is that the more you try to hack it, the harder it gets. The moment you embrace the boring fundamentals, things start to move.

If you're in the "nothing is working" phase right now — don't quit. You're closer than you think.

What phase are you in? Drop a comment. I genuinely want to know. 👇

#Growth #Mindset #RealTalk"""


def _draft_storytelling_short(topic: str) -> str:
    return f"""6 months ago: struggling with {topic}.

Today: completely different story.

The turning point? One decision I kept putting off.

What changed? I'll tell you in the comments. 👇"""


def _draft_storytelling_medium(topic: str) -> str:
    return f"""I almost quit {topic} three times.

The first time, I was overwhelmed. The learning curve felt impossible.

The second time, I had early success and then plateaued. Nothing I tried was working.

The third time, someone told me I wasn't good enough to keep going.

That last one hurt the most.

But here's what I learned:

Every person I admire in this space has a story like mine. The difference between those who made it and those who didn't isn't talent. It's the decision to keep going one more day.

What's the moment you almost quit — and didn't?

Tell me. I'll read every response. 👇"""


def _draft_storytelling_long(topic: str) -> str:
    return f"""This time last year, I was ready to give up on {topic} entirely.

I'd been working at it for 18 months. Progress was slow. Results were inconsistent. People around me were moving faster and I couldn't figure out why.

I remember sitting at my desk at 11pm thinking: "Maybe this just isn't for me."

That night I almost sent an email walking away from everything I'd built.

I didn't.

Instead, I did something I hadn't done in months: I went back to basics. I stopped trying to be clever. I stopped trying to shortcut the process. I just started doing the fundamentals, every single day, without exception.

Week 1: Nothing changed.
Week 2: Nothing changed.
Week 3: I noticed something small. Then smaller things started adding up.

Three months later, I had the best results of my career.

Here's what I know now that I didn't know then:

Most people quit at week 2. They never see what happens at week 3. The gap between failure and success in {topic} is often smaller than it seems — it's just hidden behind a wall of consistency that most people aren't willing to build.

If you're at week 2 right now — I see you. Keep going.

What's one thing that kept you going when you wanted to quit?

Share it below — your story might be exactly what someone else needs to hear today. 👇

#Resilience #Growth #{topic.split()[0].capitalize()}"""


DRAFT_FUNCTIONS = {
    ("professional", "short"):     _draft_professional_short,
    ("professional", "medium"):    _draft_professional_medium,
    ("professional", "long"):      _draft_professional_long,
    ("casual", "short"):           _draft_casual_short,
    ("casual", "medium"):          _draft_casual_medium,
    ("casual", "long"):            _draft_casual_long,
    ("storytelling", "short"):     _draft_storytelling_short,
    ("storytelling", "medium"):    _draft_storytelling_medium,
    ("storytelling", "long"):      _draft_storytelling_long,
}


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_draft(topic: str, tone: str = "professional", length: str = "medium"):
    print(f"\n{BLUE}Generating LinkedIn post — tone: {tone}, length: {length}{RESET}\n")

    # Try AI-enhanced generation first
    if OPENAI_API_KEY:
        tone_desc = {
            "professional": "formal, data-driven, executive voice",
            "casual":       "conversational, approachable, relatable",
            "storytelling": "narrative arc, personal journey, emotional",
        }.get(tone, "professional")
        length_desc = {
            "short":  "around 300 characters",
            "medium": "around 600 characters",
            "long":   "around 1200 characters",
        }.get(length, "medium")

        prompt = (
            f"Write a LinkedIn post about: {topic}\n"
            f"Tone: {tone_desc}\n"
            f"Length: {length_desc}\n"
            f"Include line breaks for readability, end with a call-to-action question.\n"
            f"Do NOT add hashtags — I'll add them separately."
        )
        content = _openai_generate(prompt)
        if content:
            print(f"{YELLOW}(AI-enhanced via OpenAI){RESET}\n")
        else:
            content = DRAFT_FUNCTIONS.get((tone, length), _draft_professional_medium)(topic)
    else:
        content = DRAFT_FUNCTIONS.get((tone, length), _draft_professional_medium)(topic)

    print("─" * 60)
    print(content)
    print("─" * 60)

    copied = copy_to_clipboard(content)
    if copied:
        print(f"\n{GREEN}Copied to clipboard!{RESET} Paste it into LinkedIn manually.")
    else:
        print(f"\n{YELLOW}Could not copy to clipboard. Install xclip (Linux) or use pbcopy (macOS).{RESET}")

    print(f"\n{YELLOW}Remember: paste this manually in LinkedIn. Never use automation — account ban risk.{RESET}")


def cmd_hashtags(topic: str):
    print(f"\n{BLUE}Generating hashtags for: {topic}{RESET}\n")

    if OPENAI_API_KEY:
        prompt = (
            f"Generate exactly 10 relevant LinkedIn hashtags for the topic: {topic}\n"
            f"Return only the hashtags, one per line, starting with #."
        )
        result = _openai_generate(prompt)
        if result:
            tags = [line.strip() for line in result.splitlines() if line.strip().startswith("#")][:10]
        else:
            tags = _generate_hashtags_template(topic)
    else:
        tags = _generate_hashtags_template(topic)

    print("Suggested hashtags:\n")
    for tag in tags:
        print(f"  {tag}")

    text = " ".join(tags)
    copied = copy_to_clipboard(text)
    if copied:
        print(f"\n{GREEN}Copied to clipboard!{RESET}")
    else:
        print(f"\n{YELLOW}Could not copy to clipboard automatically.{RESET}")


def cmd_hook(topic: str):
    print(f"\n{BLUE}Generating opening hooks for: {topic}{RESET}\n")

    if OPENAI_API_KEY:
        prompt = (
            f"Generate exactly 5 viral LinkedIn opening hooks (first line of a post) about: {topic}\n"
            f"Each hook should create curiosity or controversy. Number them 1-5."
        )
        result = _openai_generate(prompt)
        if result:
            print(result)
            copied = copy_to_clipboard(result)
            if copied:
                print(f"\n{GREEN}Copied to clipboard!{RESET}")
            return

    # Template fallback
    hooks = [t.replace("{topic}", topic).replace("{X}", "5") for t in HOOKS_TEMPLATES]
    print("5 opening hooks:\n")
    for i, hook in enumerate(hooks, 1):
        print(f"  {i}. {hook}")

    text = "\n".join(f"{i}. {h}" for i, h in enumerate(hooks, 1))
    copied = copy_to_clipboard(text)
    if copied:
        print(f"\n{GREEN}Copied to clipboard!{RESET}")
    else:
        print(f"\n{YELLOW}Could not copy to clipboard automatically.{RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter LinkedIn Content Generator")
    sub    = parser.add_subparsers(dest="command", required=True)

    # draft
    p_draft = sub.add_parser("draft", help="Generate a full LinkedIn post")
    p_draft.add_argument("topic", help="Topic or subject of the post")
    p_draft.add_argument("--tone",   choices=["professional", "casual", "storytelling"],
                         default="professional")
    p_draft.add_argument("--length", choices=["short", "medium", "long"],
                         default="medium")

    # hashtags
    p_tags = sub.add_parser("hashtags", help="Generate 10 relevant hashtags")
    p_tags.add_argument("topic")

    # hook
    p_hook = sub.add_parser("hook", help="Generate 5 viral opening hooks")
    p_hook.add_argument("topic")

    args = parser.parse_args()

    if args.command == "draft":
        cmd_draft(args.topic, args.tone, args.length)
    elif args.command == "hashtags":
        cmd_hashtags(args.topic)
    elif args.command == "hook":
        cmd_hook(args.topic)


if __name__ == "__main__":
    main()
