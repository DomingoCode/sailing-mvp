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

@app.post("/seed")
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