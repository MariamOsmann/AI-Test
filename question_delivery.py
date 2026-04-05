import pandas as pd
import time
import sys
import threading
import json
import os
from datetime import datetime
from pathlib import Path
from google import genai
from database import get_questions
from dotenv import load_dotenv
load_dotenv()  # بيقرأ الـ .env تلقائياً
# ============================================================
#   AI SQL INTERVIEWER  —  Person 1: Question Delivery
# ============================================================



STATE_FILE     = "state.json"
QUESTIONS_FILE = "sql_questions.csv"
LOG_FILE       = "interview_log.txt"

FAST_THRESHOLD = 10
SLOW_THRESHOLD = 20
LEVELS         = ["Easy", "Medium", "Hard"]

def get_time_limit(level):
    if level == "Easy":
        return 20
    elif level == "Medium":
        return 25
    else:
        return 30

# ─── Gemini Setup ─────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("  [AI]  Gemini ready ✅")
except Exception as e:
    print(f"  [WARN]  Gemini not available — using smart random.")
    client = None

# ─── Terminal UI ──────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
RED    = "\033[91m"

def _banner(text, color="white"):
    c = {"green": GREEN, "yellow": YELLOW, "cyan": CYAN,
         "white": WHITE, "red": RED}.get(color, WHITE)
    width = 56
    print(f"\n{c}{'─' * width}{RESET}")
    print(f"{c}  {text}{RESET}")
    print(f"{c}{'─' * width}{RESET}\n")

def _log(tag, text):
    tag_colors = {
        "SPEAK": CYAN, "INFO": DIM, "TIMER": YELLOW,
        "STATE": GREEN, "WARN": YELLOW, "ADAPT": CYAN, "AI": GREEN
    }
    c = tag_colors.get(tag, WHITE)
    print(f"  {c}[{tag}]{RESET}  {text}")

def _progress(current, total):
    filled = round(current / total * 24)
    bar    = "█" * filled + "░" * (24 - filled)
    pct    = round(current / total * 100)
    print(f"\n  {DIM}Progress{RESET}  {CYAN}{bar}{RESET}  "
          f"{WHITE}{current}/{total}{RESET}  {DIM}({pct}%){RESET}\n")

def _question_card(q_num, total, level, question, arrow=""):
    level_colors = {"Easy": GREEN, "Medium": YELLOW, "Hard": RED}
    lc    = level_colors.get(level, WHITE)
    width = 56
    print(f"  {DIM}{'─' * width}{RESET}")
    print(f"  {WHITE}{BOLD}Question {q_num}{RESET}  {DIM}of {total}{RESET}"
          f"   {lc}[{level}]{RESET}  {arrow}")
    print(f"  {DIM}{'─' * width}{RESET}")
    words, line = question.split(), ""
    for word in words:
        if len(line) + len(word) + 1 > 52:
            print(f"  {WHITE}{line}{RESET}")
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        print(f"  {WHITE}{line}{RESET}")
    print(f"  {DIM}{'─' * width}{RESET}\n")

# ─── AI Question Selection ────────────────────────────────
def ai_pick_question(df, used_ids, level, history, results):
    pool = df[(df["level"] == level) & (~df.index.isin(used_ids))]
    if pool.empty:
        pool = df[~df.index.isin(used_ids)]
    if pool.empty:
        pool = df

    if not client:
        return pool.sample(1).iloc[0], ""

    available   = pool["question"].tolist()
    history_str = ", ".join(history) if history else "None yet"
    performance = ", ".join([
        f"{r['level']}:{round(r['elapsed'], 1)}s" for r in results
    ]) if results else "No data yet"

    prompt = f"""
You are an AI SQL interviewer assistant.

Student level: {level}
Previous performance: {performance}
Questions already asked: {history_str}
Available questions: {json.dumps(available)}

Choose the BEST next question for the student based on their performance.
Reply exactly in this format:

QUESTION: <exact question text>
REASON: <short reason>
"""

    try:
        response      = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt
        )
        content       = response.text.strip()
        question_line = ""
        reason_line   = ""

        for line in content.splitlines():
            line_clean = line.strip().lower()
            if line_clean.startswith("question:"):
                question_line = line.split(":", 1)[1].strip()
            elif line_clean.startswith("reason:"):
                reason_line = line.split(":", 1)[1].strip()

        chosen_clean = question_line.strip().lower().replace("?", "").replace(".", "")
        pool_clean   = (
            pool["question"]
            .str.strip().str.lower()
            .str.replace("?", "", regex=False)
            .str.replace(".", "", regex=False)
        )

        match = pool[pool_clean == chosen_clean]
        if not match.empty:
            if reason_line:
                _log("AI", reason_line)
            return match.iloc[0], reason_line

    except Exception as e:
        _log("WARN", f"Gemini error — using smart random")

    return pool.sample(1).iloc[0], ""

# ─── TTS ──────────────────────────────────────────────────
def setup_speaker():
    try:
        import subprocess
        test = 'Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak("ready")'
        subprocess.run(["powershell", "-Command", test], capture_output=True, timeout=10)
        _log("INFO", "TTS ready ✅  (PowerShell)")
        return "powershell"
    except Exception as e:
        _banner(f"TTS unavailable: {e}", "yellow")
        return None

def speak(spk, text):
    _log("SPEAK", text)
    try:
        import subprocess
        # escape single quotes in text
        safe = text.replace("'", " ")
        ps_cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe}')"
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=30)
    except Exception as e:
        _log("WARN", f"TTS error: {e}")

# ─── State File ───────────────────────────────────────────
def write_state(status, q_num=0, question="", level="", name=""):
    state = {
        "status":       status,
        "question_num": q_num,
        "question":     question,
        "level":        level,
        "student_name": name,
        "timestamp":    datetime.now().isoformat(),
    }
    Path(STATE_FILE).write_text(
        json.dumps(state, indent=2, ensure_ascii=False)
    )

# ─── Log ──────────────────────────────────────────────────
def save_log(name, q_num, question, level, answer, elapsed, adapted, reason):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"{name} | Q{q_num} | [{level}] | {question} | "
            f"{answer} | {elapsed:.2f}s | adapt:{adapted} | "
            f"reason:{reason}\n"
        )

# ─── Countdown Timer ──────────────────────────────────────
def countdown_timer(seconds, stop_event):
    for remaining in range(int(seconds), 0, -1):
        if stop_event.is_set():
            break
        filled  = round((seconds - remaining) / seconds * 10)
        bar     = "█" * filled + "░" * (10 - filled)
        urgency = RED if remaining <= 10 else YELLOW if remaining <= 20 else GREEN
        print(f"  {urgency}⏱  [{bar}]  {remaining:2d}s{RESET}", flush=True)
        time.sleep(1)
    print(f"  {DIM}⏱  [{'█' * 10}]  Done{RESET}", flush=True)

# ─── Answer Input ─────────────────────────────────────────
def get_answer(spk, question, q_num, level, time_limit):
    remaining_time = time_limit
    total_elapsed  = 0

    while True:
        stop_event   = threading.Event()
        timer_thread = threading.Thread(
            target=countdown_timer,
            args=(remaining_time, stop_event),
            daemon=True,
        )

        print(f"  {DIM}Type your answer — or  {RESET}"
              f"{CYAN}r{RESET}{DIM}  to repeat the question{RESET}\n")
        time.sleep(0.4)

        def auto_timeout(secs):
            time.sleep(secs + 0.3)
            if not stop_event.is_set():
                try:
                    import msvcrt
                    msvcrt.putch(b'\r')  # Windows
                except ImportError:
                    import os, signal
                    os.kill(os.getpid(), signal.SIGINT)  # Linux/Mac

        threading.Thread(target=auto_timeout, args=(remaining_time,), daemon=True).start()

        timer_thread.start()
        start  = time.perf_counter()
        answer = input(f"  {CYAN}>{RESET}  ").strip()

        stop_event.set()
        timer_thread.join()

        elapsed        = time.perf_counter() - start
        total_elapsed += elapsed
        remaining_time = max(0, remaining_time - elapsed)

        if remaining_time <= 0:
            print(f"\n  {RED}⏰ Time's up! Moving on...{RESET}\n")
            speak(spk, "Time is up.")
            return "", total_elapsed

        if answer.lower() == "r":
            if remaining_time <= 5:
                speak(spk, "Time is almost over. No repeats allowed.")
                print(f"\n  {RED}Less than 5 seconds — no repeats!{RESET}\n")
                return "", total_elapsed
            print(f"\n  {YELLOW}Repeating... ({round(remaining_time)}s remaining){RESET}\n")
            speak(spk, f"Question again. {question}")
            continue

        return answer, total_elapsed

# ─── Adaptive Difficulty ──────────────────────────────────
def get_next_level(current_level, elapsed):
    idx = LEVELS.index(current_level)
    if elapsed < FAST_THRESHOLD:
        new_idx = min(idx + 1, len(LEVELS) - 1)
        arrow   = f"{GREEN}⬆ Upgrading to {LEVELS[new_idx]}{RESET}"
        adapted = "up"
    elif elapsed > SLOW_THRESHOLD:
        new_idx = max(idx - 1, 0)
        arrow   = f"{YELLOW}⬇ Downgrading to {LEVELS[new_idx]}{RESET}"
        adapted = "down"
    else:
        new_idx = idx
        arrow   = ""
        adapted = "same"
    return LEVELS[new_idx], arrow, adapted

# ─── Load Questions ───────────────────────────────────────
def load_questions():
    try:
        df = get_questions()
        df["level"] = df["level"].str.capitalize()
        if df.empty:
            _banner("No questions in CSV", "red")
            sys.exit(1)
    except FileNotFoundError:
        _banner(f"ERROR  '{QUESTIONS_FILE}' not found", "red")
        sys.exit(1)
    except Exception as e:
        _banner(f"ERROR  {e}", "red")
        sys.exit(1)

    missing = {"question", "level"} - set(df.columns)
    if missing:
        _banner(f"ERROR  CSV missing columns: {missing}", "red")
        sys.exit(1)
    return df

# ─── Summary ──────────────────────────────────────────────
def print_summary(name, total_time, results):
    _banner("INTERVIEW SUMMARY", "cyan")
    print(f"  {DIM}Student    {RESET}{WHITE}{name}{RESET}")
    print(f"  {DIM}Total time {RESET}{WHITE}{total_time:.0f}s{RESET}")
    print(f"  {DIM}Questions  {RESET}{WHITE}{len(results)}{RESET}\n")
    print(f"  {DIM}{'─' * 56}{RESET}")
    for r in results:
        level_colors = {"Easy": GREEN, "Medium": YELLOW, "Hard": RED}
        lc     = level_colors.get(r["level"], WHITE)
        timing = f"{GREEN}fast{RESET}"   if r["elapsed"] < FAST_THRESHOLD else \
                 f"{RED}slow{RESET}"     if r["elapsed"] > SLOW_THRESHOLD else \
                 f"{DIM}normal{RESET}"
        print(
            f"  Q{r['q_num']}  {lc}[{r['level']:6}]{RESET}  "
            f"{timing}  {DIM}{r['elapsed']:.1f}s{RESET}"
        )
    print(f"  {DIM}{'─' * 56}{RESET}\n")

# ─── Main ─────────────────────────────────────────────────
def run_interview(student_name: str = None):
    spk           = setup_speaker()
    df            = load_questions()
    total         = 5
    used_ids      = set()
    results       = []
    history       = []
    current_level = "Medium"
    arrow         = ""

    _banner("AI SQL INTERVIEWER", "cyan")
    speak(spk, "Welcome to your SQL technical interview.")
    write_state("idle")

    # لو جاي من الـ API بياخد الاسم منه، لو من الـ terminal بيسأل
    if student_name:
        name = student_name
    else:
        while not (name := input(f"  {DIM}Your name:{RESET}  ").strip()):
            print(f"  {RED}Name cannot be empty.{RESET}")

    speak(spk, f"Hello {name}. The interview will begin now.")
    _log("INFO", f"Student: {WHITE}{name}{RESET}  |  "
                 f"Questions: {total}  |  Time limit: depends on level")
    time.sleep(1)

    interview_start = time.perf_counter()

    for idx in range(total):
        q_num = idx + 1

        _log("AI", f"Analyzing performance → selecting best "
                   f"{WHITE}{current_level}{RESET} question...")

        row, reason  = ai_pick_question(df, used_ids, current_level, history, results)
        used_ids.add(row.name)
        question = row["question"]
        level    = row["level"]
        history.append(question)

        _progress(q_num, total)
        if arrow:
            _log("ADAPT", arrow)

        _question_card(q_num, total, level, question)

        write_state("waiting",   q_num, question, level, name)
        speak(spk, f"Question {q_num}. {question}")

        time_limit = get_time_limit(level)

        speak(spk, f"You have {time_limit} seconds to answer.")
        write_state("recording", q_num, question, level, name)

        answer, elapsed = get_answer(spk, question, q_num, level, time_limit)

        write_state("waiting", q_num, question, level, name)

        current_level, arrow, adapted = get_next_level(current_level, elapsed)

        save_log(name, q_num, question, level, answer, elapsed, adapted, reason)
        results.append({
            "q_num":   q_num,
            "level":   level,
            "elapsed": elapsed,
        })

        if elapsed > time_limit:
            speak(spk, f"Time is over. You took {round(elapsed)} seconds.")
            _log("TIMER", f"{RED}Over limit{RESET}  {elapsed:.1f}s")
        else:
            speak(spk, f"Answer recorded in {round(elapsed)} seconds.")
            _log("TIMER", f"{GREEN}In time{RESET}  {elapsed:.1f}s")

        if idx < total - 1:
            speak(spk, "Next question.")
            print(f"\n  {DIM}Please get ready...{RESET}")
            time.sleep(2)

    total_time = time.perf_counter() - interview_start
    write_state("done", q_num, "", "", name)
    _banner("INTERVIEW FINISHED", "green")
    speak(spk, f"The interview is finished. Thank you {name} for your time.")
    print_summary(name, total_time, results)
    _log("INFO", f"Log saved to {WHITE}{LOG_FILE}{RESET}")

# ─── Entry Point ──────────────────────────────────────────
if __name__ == "__main__":
    run_interview()