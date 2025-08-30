# import packages and modules
import asyncio
import os
from agents import Agent, Runner, WebSearchTool, function_tool, ItemHelpers
from openai import OpenAI
from dotenv import load_dotenv


from dotenv import load_dotenv
import os

load_dotenv()
print("OPENAI_API_KEY starts with:", os.getenv("OPENAI_API_KEY")[:8])



# get openAPI key
load_dotenv()
openai_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_key)

# define tools for agents


#tool be my NBA level basketball coach and trainer
# coach_trainer.py  (paste over your file)




import os, time, re, requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

# ========= ENV & CLIENTS =========
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in .env")
BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY")  # optional but recommended

client = OpenAI(api_key=OPENAI_API_KEY)

# ========= BALLDONTLIE (light) =========
BALD_BASE = "https://api.balldontlie.io/v1"

class BallDontLie:
    def __init__(self):
        self.base = BALD_BASE.rstrip("/")
        self.s = requests.Session()
        hdrs = {"Accept": "application/json"}
        if BALLDONTLIE_API_KEY:
            hdrs["Authorization"] = BALLDONTLIE_API_KEY
        self.s.headers.update(hdrs)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base}/{path.lstrip('/')}"
        r = self.s.get(url, params=params or {}, timeout=20)
        if r.status_code == 429:
            time.sleep(0.5); r = self.s.get(url, params=params or {}, timeout=20)
        if r.status_code >= 400:
            # Pass back some detail but don't crash the app
            return {"error": f"[{r.status_code}] {url}", "body": r.text[:300], "data": []}
        return r.json()

    def resolve_player(self, first_name: str, last_name: str) -> Optional[Dict[str, Any]]:
        # search by last name
        data = self._get("players", {"per_page": 100, "search": last_name})
        for p in data.get("data", []):
            if p.get("first_name","").lower()==first_name.lower() and p.get("last_name","").lower()==last_name.lower():
                return p
        # strict filter
        data = self._get("players", {"per_page": 100, "first_name": first_name, "last_name": last_name})
        if data.get("data"): return data["data"][0]
        return None

    def season_averages(self, player_id: int, season: int) -> Optional[Dict[str, Any]]:
        data = self._get("season_averages", {"season": season, "player_ids[]": player_id})
        if "error" in data: return None
        arr = data.get("data", [])
        return arr[0] if arr else None

    def player_game_logs(self, player_id: int, season: int) -> List[Dict[str, Any]]:
        out, cursor = [], None
        while True:
            params={"player_ids[]": player_id, "seasons[]": season, "per_page": 100}
            if cursor: params["cursor"]=cursor
            data = self._get("stats", params)
            if "error" in data: break
            out.extend(data.get("data", []))
            meta = data.get("meta") or {}
            cursor = meta.get("next_cursor")
            if not cursor: break
            time.sleep(0.15)
        out.sort(key=lambda x: x.get("game",{}).get("date",""))
        return out

# ========= COACH PROMPTS =========
SYSTEM_PROMPT = """You are an NBA-level basketball coach and trainer.
Be concise, actionable, and specific. Use sports science (progressive overload, specificity, recovery).
When stats are present, reference them; if not, state assumptions and rely on best-practice principles.
Always provide: (1) diagnosis or answer, (2) 2–4 coaching cues, (3) 1–3 quick drills or next steps."""

SHOT_DIAG_PROMPT = """The user reports jump shot issues: {issue}.
They are 6'4". Provide:
- Top likely causes tied to biomechanics and timing
- 3–5 coaching cues
- A 10–12 minute micro-drill stack (reps & constraints)
- 2 KPI targets (arc/accuracy/consistency)
Keep it tight and practical."""

MIRROR_PROMPT = """User wants to mirror the NBA player: {player_name}.
Season {season} context (if stats missing, assume typical style for that player archetype).
Return:
1) Snapshot of style (role, strengths, liabilities)
2) 7-day microcycle (skill + S&C + recovery each day)
3) 4–6 drills keyed to that style (reps, constraints, cues)
4) 2–3 in-game reads/tweaks
5) 4 KPI targets (per game & per week)
If stats are available from balldontlie, reference them briefly."""

GENERAL_QA_PROMPT = """Answer the user's basketball question:
Q: {question}
Return: a crisp answer, 3 coaching cues, and 2 drill ideas or next steps."""

# ========= ROUTER =========
def route_intent(user_text: str) -> str:
    t = user_text.lower().strip()
    if re.search(r"\bmirror\b|\bplay like\b|\bmodel my game after\b", t):
        return "mirror"
    if re.search(r"\bjumper\b|\bjump shot\b|\bjumpshot\b|\bshot\b|\bform\b|\brelease\b", t):
        return "shot"
    return "qa"

# ========= HANDLERS =========
bdl = BallDontLie()

def handle_shot_issue(text: str) -> str:
    prompt = SHOT_DIAG_PROMPT.format(issue=text)
    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role":"system","content":SYSTEM_PROMPT},
                   {"role":"user","content":prompt}],
            temperature=0.4
        )
        return resp.output_text
    except Exception:
        # cheap fallback
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":SYSTEM_PROMPT},
                      {"role":"user","content":prompt}],
            temperature=0.4
        )
        return resp.choices[0].message.content

def handle_mirror(text: str) -> str:
    # pull player name from text: look for "mirror X" or "like X"
    m = re.search(r"(?:mirror|play like|model my game after)\s+([a-zA-Z'\- ]+)", text.lower())
    player_raw = m.group(1).strip() if m else "Jordan Poole"
    # title case
    player_name = " ".join(w.capitalize() for w in player_raw.split())

    # split first/last if possible
    parts = player_name.split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        player = bdl.resolve_player(first, last)
    else:
        player = None
    season = 2024
    avg, logs = None, []
    if player:
        pid = player["id"]
        avg = bdl.season_averages(pid, season)
        logs = bdl.player_game_logs(pid, season)

    prompt = MIRROR_PROMPT.format(player_name=player_name, season=season)
    # tack on light stat summary if we have it
    ctx = ""
    if avg:
        ctx = (f"\nData: PTS {avg.get('pts','NA')} REB {avg.get('reb','NA')} AST {avg.get('ast','NA')} "
               f"FG% {avg.get('fg_pct','NA')} 3P% {avg.get('fg3_pct','NA')} TO {avg.get('turnover','NA')}")
    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role":"system","content":SYSTEM_PROMPT},
                   {"role":"user","content":prompt + ctx}],
            temperature=0.45
        )
        return resp.output_text
    except Exception:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":SYSTEM_PROMPT},
                      {"role":"user","content":prompt + ctx}],
            temperature=0.45
        )
        return resp.choices[0].message.content

def handle_general_qa(text: str) -> str:
    prompt = GENERAL_QA_PROMPT.format(question=text)
    try:
        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=[{"role":"system","content":SYSTEM_PROMPT},
                   {"role":"user","content":prompt}],
            temperature=0.4
        )
        return resp.output_text
    except Exception:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":SYSTEM_PROMPT},
                      {"role":"user","content":prompt}],
            temperature=0.4
        )
        return resp.choices[0].message.content

# ========= CLI LOOP =========
def main():
    print("🏀 Coach/Trainer is live. Ask anything. Examples:")
    print(" • “My 3 comes up short, what am I doing wrong?”")
    print(" • “Mirror Jordan Poole” or “I want to play like Shai Gilgeous-Alexander”")
    print(" • “How do I improve first-step speed?”")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            q = input("You > ").strip()
            if q.lower() in {"exit","quit"}: break
            if not q: continue

            intent = route_intent(q)
            if intent == "shot":
                out = handle_shot_issue(q)
            elif intent == "mirror":
                out = handle_mirror(q)
            else:
                out = handle_general_qa(q)

            print("\nCoach > " + out + "\n")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nCoach > Error: {e}\n")

if __name__ == "__main__":
    main()


