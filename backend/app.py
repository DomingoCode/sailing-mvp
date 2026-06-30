import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2

app = FastAPI()

# CORS (обязательно для фронта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/listings")
def listings():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT title, location, dates, price, source_url
        FROM listings
        ORDER BY id DESC
        LIMIT 100
    """)

    rows = cur.fetchall()

    return [
        {
            "title": r[0],
            "location": r[1],
            "dates": r[2],
            "price": r[3],
            "url": r[4]
        }
        for r in rows
    ]


@app.get("/search")
def search(q: str):
    conn = get_conn()
    cur = conn.cursor()

    q = f"%{q.lower()}%"

    cur.execute("""
        SELECT title, location, dates, price, source_url
        FROM listings
        WHERE
            LOWER(title) LIKE %s
            OR LOWER(location) LIKE %s
            OR LOWER(dates) LIKE %s
        ORDER BY id DESC
        LIMIT 100
    """, (q, q, q))

    rows = cur.fetchall()

    return [
        {
            "title": r[0],
            "location": r[1],
            "dates": r[2],
            "price": r[3],
            "url": r[4]
        }
        for r in rows
    ]

@app.get("/seed")
def seed():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO listings (title, location, dates, price, source_url)
        VALUES
        ('Sailing Greece Adventure', 'Greece', 'July 10-17', '600€', 'https://example.com/1'),
        ('Croatia Catamaran Trip', 'Croatia', 'August 1-8', '750€', 'https://example.com/2')
    """)

    conn.commit()
    cur.close()
    conn.close()

    return {"status": "seeded"}

@app.get("/ai-search")
def ai_search(q: str):
    q = q.lower()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT title, location, dates, price, source_url
        FROM listings
        ORDER BY id DESC
        LIMIT 100
    """)

    rows = cur.fetchall()

    results = []

    for r in rows:
        text = " ".join([str(x).lower() for x in r if x])

        score = 0

        # VERY SIMPLE "AI" scoring layer (v1)
        if any(word in text for word in q.split()):
            score += 1

        if "greece" in q and "greece" in text:
            score += 3

        if "calm" in q and "party" not in text:
            score += 2

        if "budget" in q:
            score += 1

        results.append({
            "title": r[0],
            "location": r[1],
            "dates": r[2],
            "price": r[3],
            "url": r[4],
            "score": score
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    return results


from google import genai
import os
import json
import re

client = genai.Client(
    api_key=os.getenv("OPENAI_API_KEY")
)

@app.post("/ai-parse")
def ai_parse(payload: dict):
    try:
        user_query = payload.get("q", "")

        prompt = f"""
Extract information from the following sailing trip request.

Return ONLY valid JSON.

Schema:

{{
  "location": string|null,
  "budget": number|null,
  "duration_days": number|null,
  "vibe": string|null
}}

User:
{user_query}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)

        if not match:
            return {
                "error": "No JSON returned",
                "raw": text
            }

        return json.loads(match.group())

    except Exception as e:
        return {
            "error": str(e)
        }

@app.post("/search-ai")
def search_ai(payload: dict):
    q = payload.get("q", "")

    # 1. AI parse
    parsed = ai_parse({"q": q})

    location = parsed.get("location")
    budget = parsed.get("budget")
    duration = parsed.get("duration_days")
    vibe = parsed.get("vibe")

    conn = get_conn()
    cur = conn.cursor()

    # 2. базовый SQL (простая фильтрация MVP уровня)
    query = """
        SELECT title, location, dates, price, source_url
        FROM listings
        WHERE 1=1
    """

    params = []

    if location:
        query += " AND LOWER(location) LIKE %s"
        params.append(f"%{location.lower()}%")

    if budget:
        query += " AND CAST(price AS INTEGER) <= %s"
        params.append(budget)

    cur.execute(query, params)
    rows = cur.fetchall()

    # 3. ranking (очень простой MVP score)
    results = []

    for r in rows:
        score = 0

        text = " ".join([str(x).lower() for x in r if x])

        if location and location.lower() in text:
            score += 3

        if vibe and vibe.lower() in text:
            score += 2

        results.append({
            "title": r[0],
            "location": r[1],
            "dates": r[2],
            "price": r[3],
            "url": r[4],
            "score": score
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    return results