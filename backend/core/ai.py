"""The billboard's voice + moderation. Anthropic Claude via the Emergent universal key."""
import os
import json
import re
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
log = logging.getLogger("billboard.ai")

MODEL = ("anthropic", "claude-sonnet-4-6")

# Hard word-list gate that runs before any model call.
WORDLIST = [
    "nigger", "nigga", "faggot", "tranny", "kike", "chink", "spic", "retard",
    "rape", "child porn", "cp link", "kill yourself", "kys", "kill you",
    "i will kill", "gas the", "heil hitler", "pedo",
]

BLOCK_COPY = "The wall has standards. Barely, but it has them."

WALL_PERSONA = (
    "You are The Last Billboard: a washed-up wall on a construction hoarding that has "
    "held Coke ads, gig posters and divorce lawyers for decades. You are dry, tired and "
    "precise. Short sentences. Never zany. Never enthusiastic. No exclamation marks. "
    "No emoji. No puns on people's names. You mock the message, the price and the "
    "ambition. You never mock a person's identity, appearance, race, gender or anything "
    "you cannot see. You never say anything negative about a real business, product or "
    "person named in a message: if someone promotes their cafe, you are dry about the "
    "message and the wall, never about the cafe."
)

VOICE_INSTRUCTIONS = """Return ONLY a JSON object, no prose, no markdown fences, with exactly these keys:
{"ad_line": string, "heckle": string, "obituary": string}

- ad_line: the NEW message rewritten as a real advertising slogan. Max 15 words. Dry. It may be genuinely good.
- heckle: one line addressed to the DETHRONED message. It MUST reference that specific message's wording or its exact reign duration. Max 20 words. Generic burns are a failure.
- obituary: a one-sentence epitaph for the DETHRONED message, for the Hall of the Fallen. Max 20 words. It MUST quote the dethroned message itself in single quotes, in the form: Here lies 'buy $DOGE'. It never learned.

If there is no dethroned message (this is the first poster ever), set heckle and obituary to empty strings.
No exclamation marks anywhere. No emoji. Plain ASCII quotes."""

MOD_INSTRUCTIONS = """You are the moderation gate for a public billboard. Return ONLY JSON:
{"verdict": "ALLOW" or "BLOCK", "reason": short string}

ALLOW:
- jokes, nonsense, absurdity, proposals, manifestos, confessions, shoutouts
- self-promotion of any kind
- POSITIVE or PROMOTIONAL messages about real businesses, products, projects, bands, apps, cafes
- expressing liking or admiration for a real brand ("i love Nike")

BLOCK:
- ANY negative, accusatory, mocking or critical statement about a real business, product, brand or person (e.g. "X is a scam", "Y's food is bad", naming a competitor to knock it)
- hate or slurs targeting any group
- sexual content
- threats or incitement of violence
- private individuals' personal information (phone, address, full name of a private person as a target)
- spam link farms, obvious phishing, crypto airdrop scams
- impersonating a brand or public figure the poster does not own (claiming to BE Nike). Saying you love Nike is fine.

The rule: you may buy the wall to promote anything. You may not buy it to attack anything.
When genuinely ambiguous, ALLOW. Judge the text as written, not imagined intent."""


def _key() -> str:
    k = os.environ.get("EMERGENT_LLM_KEY", "")
    if not k:
        raise RuntimeError("EMERGENT_LLM_KEY missing")
    return k


def _chat(session_id: str, system: str):
    from emergentintegrations.llm.chat import LlmChat

    return LlmChat(api_key=_key(), session_id=session_id, system_message=system).with_model(*MODEL)


def _extract_json(raw: str) -> dict:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError("no json in model output: %r" % raw[:300])


def _clean(s: str, max_words: int) -> str:
    s = (s or "").strip().strip('"').replace("!", ".").replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    words = s.split()
    if len(words) > max_words:
        s = " ".join(words[:max_words]).rstrip(",.;:") + "."
    return s


def wordlist_hit(*texts) -> str | None:
    blob = " ".join([(t or "") for t in texts]).lower()
    for w in WORDLIST:
        if w in blob:
            return w
    return None


async def moderate(text: str, name: str = "", image_url: str = "") -> dict:
    """-> {allow: bool, reason: str, stage: 'wordlist'|'ai'|'error'}"""
    hit = wordlist_hit(text, name, image_url)
    if hit:
        return {"allow": False, "reason": "word-list: %s" % hit, "stage": "wordlist"}
    payload = json.dumps({"message": text, "name": name, "image_url": image_url})
    try:
        from emergentintegrations.llm.chat import UserMessage

        chat = _chat("mod-%s" % abs(hash(payload)), MOD_INSTRUCTIONS)
        raw = await chat.send_message(UserMessage(text="Judge this submission:\n" + payload))
        data = _extract_json(raw if isinstance(raw, str) else str(raw))
        verdict = str(data.get("verdict", "")).upper().strip()
        if verdict not in ("ALLOW", "BLOCK"):
            raise ValueError("bad verdict %r" % verdict)
        return {"allow": verdict == "ALLOW", "reason": str(data.get("reason", ""))[:200], "stage": "ai"}
    except Exception as e:  # fail open, the wall has standards, barely
        log.warning("moderation failed, failing open: %s", e)
        return {"allow": True, "reason": "moderator unavailable", "stage": "error"}


def human_reign(seconds: float | int | None) -> str:
    if seconds is None:
        return ""
    s = int(max(0, seconds))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return "%dd %dh" % (d, h)
    if h:
        return "%dh %dm" % (h, m)
    if m:
        return "%dm %ds" % (m, s)
    return "%ds" % s


async def voice(new_text: str, old_text: str | None, old_name: str | None,
                reign_seconds: float | None, amount_label: str = "") -> dict:
    """One call per takeover. -> {ad_line, heckle, obituary}"""
    reign = human_reign(reign_seconds) if old_text else ""
    payload = {
        "new_message": new_text,
        "price_paid": amount_label,
        "dethroned_message": old_text or None,
        "dethroned_holder_name": old_name or None,
        "dethroned_reign_duration": reign or None,
    }
    try:
        from emergentintegrations.llm.chat import UserMessage

        chat = _chat("voice-%s" % abs(hash(json.dumps(payload))), WALL_PERSONA + "\n\n" + VOICE_INSTRUCTIONS)
        raw = await chat.send_message(UserMessage(text=json.dumps(payload)))
        data = _extract_json(raw if isinstance(raw, str) else str(raw))
        return {
            "ad_line": _clean(data.get("ad_line", ""), 15),
            "heckle": _clean(data.get("heckle", ""), 20) if old_text else "",
            "obituary": _clean(data.get("obituary", ""), 20) if old_text else "",
        }
    except Exception as e:
        log.warning("voice failed, falling back: %s", e)
        return {
            "ad_line": "",
            "heckle": ("Held %s. The wall moved on." % reign) if old_text else "",
            "obituary": ("Here lies '%s'. Painted over." % (old_text or "")[:60]) if old_text else "",
        }


async def recap(events: list[dict]) -> str:
    """Admin 'last hour on the wall' recap, mono plain text."""
    if not events:
        return "Nothing happened on the wall in the last hour. It has seen worse hours."
    try:
        from emergentintegrations.llm.chat import UserMessage

        system = WALL_PERSONA + (
            "\n\nWrite a short recap of the last hour on the wall for posting online. "
            "3 to 5 short lines, plain text, no markdown, no emoji, no exclamation marks. "
            "Name the messages and the prices. Dry and tired. End with the current price."
        )
        chat = _chat("recap-%d" % abs(hash(json.dumps(events, default=str))), system)
        raw = await chat.send_message(UserMessage(text=json.dumps(events, default=str)))
        return (raw if isinstance(raw, str) else str(raw)).strip()
    except Exception as e:
        log.warning("recap failed: %s", e)
        lines = ["Last hour on the wall:"]
        for e2 in events:
            lines.append("- %s took it for %s" % (e2.get("name"), e2.get("price")))
        return "\n".join(lines)
