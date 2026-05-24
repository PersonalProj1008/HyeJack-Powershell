import os
import psycopg2
from typing import Dict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from psycopg2.extras import RealDictCursor


app = FastAPI()

# Ensure directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Database Connection Params ---
def get_db_params():
    return {
        "host": os.getenv("PG_HOST", "postgres_db"),
        "database": os.getenv("PG_DB", "poweragent_kb"),
        "user": os.getenv("PG_USER", "poweradmin"),
        "password": os.getenv("PG_PASSWORD", "StaticPassword123!")
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
    request=request,
    name="index.html",
    context={"request": request}
    )


# ====================== UPDATED ENDPOINTS ======================

@app.get("/api/topics")
async def get_topics(offset: int = 0, limit: int = 20):
    """Get list of topics with their latest message timestamp"""
    try:
        conn = psycopg2.connect(**get_db_params())
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                t.TOPIC as Topic_Name,
                MAX(c.id) as last_msg_id,
                MAX(c.DateTime) as last_message_time
            FROM Topics t
            LEFT JOIN Conversations c ON t.TOPIC = c.Topic_Name
            GROUP BY t.TOPIC
            ORDER BY last_msg_id DESC NULLS LAST, t.TOPIC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/messages/{topic}")
async def get_messages(topic: str, offset: int = 0, limit: int = 20):
    """Get messages for a specific topic"""
    try:
        conn = psycopg2.connect(**get_db_params())
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                id, 
                Content, 
                Is_User, 
                Is_Bot,
                DateTime 
            FROM Conversations 
            WHERE Topic_Name = %s 
                AND Content IS NOT NULL  -- Filter out null content
                AND Content != ''        -- Filter out empty content
            ORDER BY id DESC, DateTime DESC  -- Reverse chronological order (newest first)
            LIMIT %s OFFSET %s
        """, (topic, limit, offset))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# ====================== NEW HELPER ENDPOINTS ======================

@app.get("/api/current-topic")
async def get_current_topic():
    """Get the currently active topic"""
    try:
        conn = psycopg2.connect(**get_db_params())
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT TOPIC_NAME FROM CURRENT_TOPIC WHERE ID = 1")
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if row:
            return {"topic_name": row["topic_name"]}
        return {"topic_name": None}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/current-topic")
async def set_current_topic(topic_name: str):
    """Set the current active topic"""
    try:
        conn = psycopg2.connect(**get_db_params())
        cur = conn.cursor()
        
        # Upsert: Update if exists, insert if not (ID must be 1 due to CHECK constraint)
        cur.execute("""
            INSERT INTO CURRENT_TOPIC (ID, TOPIC_NAME)
            VALUES (1, %s)
            ON CONFLICT (ID) 
            DO UPDATE SET TOPIC_NAME = EXCLUDED.TOPIC_NAME
        """, (topic_name,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "success", "topic_name": topic_name}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/test")
def test():
    return {"message": "FastAPI is working - Updated with new schema"}


# Optional: Endpoint to list all topics from Topics table (without conversation data)
@app.get("/api/all-topics")
async def get_all_topics():
    try:
        conn = psycopg2.connect(**get_db_params())
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT ID, TOPIC, COLLECTION_NAME, COLLECTION_ID, KNOWLEDGE_BASE_FILES 
            FROM Topics 
            ORDER BY TOPIC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
