# AI SQL Interviewer 🎤💻

Person 1 — Question Delivery Module

---

## 📋 المسؤوليات

- اختيار 5 أسئلة SQL بالذكاء الاصطناعي (Gemini)
- قراءة الأسئلة بصوت (Text-to-Speech)
- عرض الأسئلة بشكل متسلسل وانتظار إجابة الطالب
- Adaptive difficulty — يرفع أو ينزل الصعوبة حسب أداء الطالب

---

## 📂 الملفات

| الملف | الوظيفة |
|---|---|
| `question_delivery.py` | الكود الرئيسي |
| `api.py` | FastAPI endpoints للتيم |
| `database.py` | تهيئة قاعدة البيانات |
| `sql_questions.csv` | بنك الأسئلة |
| `state.json` | حالة الانترفيو real-time (للتيم) |
| `interview_log.txt` | سجل كامل بعد الانتهاء (للتيم) |

---

## ⚙️ Setup

1. ثبّت الـ dependencies:
```
pip install -r requirements.txt
```

2. انسخ ملف `.env.example` وسمّيه `.env` وحط الـ API Key بتاعك:
```
GEMINI_API_KEY=your_api_key_here
```

3. هيّئ قاعدة البيانات (مرة واحدة بس):
```
python database.py
```

4. شغّل الانترفيو:
```
python question_delivery.py
```

5. أو شغّل الـ API للتيم:
```
uvicorn api:app --reload
```

---

## 🔗 Integration مع التيم

### API Endpoints — على `http://localhost:8000`

| Endpoint | Method | مين بيستخدمه | بيعمل إيه |
|---|---|---|---|
| `/start?student_name=alaa` | POST | Frontend | بيبدأ الانترفيو ويرجع session_id |
| `/state/{session_id}` | GET | Frontend + كاميرا | بيجيب الحالة دلوقتي |
| `/results/{student_name}` | GET | Backend | بيجيب نتايج الطالب |
| `/questions` | GET | أي حد | بيجيب كل الأسئلة |

### مثال على `/start`
```json
{
  "message": "Interview started",
  "session_id": "abc-123-xyz"
}
```

### مثال على `/state/{session_id}`
```json
{
  "status": "recording",
  "question_num": 3,
  "question": "What is RANK()?",
  "level": "Hard",
  "student_name": "alaa",
  "session_id": "abc-123-xyz",
  "timestamp": "2026-04-04T01:00:00"
}
```
الـ status ممكن يكون: `idle` / `waiting` / `recording` / `done`

### مثال على `/results/{student_name}`
```json
{
  "student": "alaa",
  "results": [
    {
      "question_num": "Q1",
      "level": "[Medium]",
      "question": "What is RANK()?",
      "answer": "...",
      "elapsed": "4.04s"
    }
  ]
}
```

---

## ⏱️ Time Limits

| Level | Time |
|---|---|
| Easy | 20s |
| Medium | 25s |
| Hard | 30s |

---

## 👩‍💻 Author
Alaa