from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import threading
from pathlib import Path
import uuid

from question_delivery import run_interview
from shared import answers_store
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE_FILE = "state.json"
LOG_FILE   = "interview_log.txt"

# ─── START INTERVIEW ──────────────────────────────────────
@app.post("/start")
def start_interview(student_name: str):
    session_id = str(uuid.uuid4())

    def run():
        run_interview(student_name, session_id)

    threading.Thread(target=run, daemon=True).start()

    return {
        "message": "Interview started",
        "session_id": session_id
    }

# ─── GET STATE (IMPORTANT 🔥) ─────────────────────────────
@app.get("/state/{session_id}")
def get_state(session_id: str):
    try:
        state = json.loads(Path(STATE_FILE).read_text(encoding="utf-8"))

        if state.get("session_id") == session_id:
            return state
        else:
            return {"status": "not_found"}

    except Exception:
        return {"status": "idle"}

# ─── RESULTS ─────────────────────────────────────────────
@app.get("/results/{student_name}")
def get_results(student_name: str):
    try:
        results = []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" | ")
                if len(parts) >= 7 and parts[1] == student_name:
                    results.append({
                        "timestamp":    parts[0],
                        "student":      parts[1],
                        "question_num": parts[2],
                        "level":        parts[3],
                        "question":     parts[4],
                        "answer":       parts[5],
                        "elapsed":      parts[6],
                        "adapted":      parts[7] if len(parts) > 7 else "",
                    })
        return {"student": student_name, "results": results}
    except Exception:
        return {"student": student_name, "results": []}

# ─── QUESTIONS ───────────────────────────────────────────
@app.get("/questions")
def get_questions_list():
    from database import get_questions
    df = get_questions()
    return {"questions": df.to_dict(orient="records")}

@app.post("/answer")
def submit_answer(student_name: str, answer: str):
    answers_store[student_name] = answer
    return {"message": "Answer received"}