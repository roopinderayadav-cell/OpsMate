import sqlite3, json
from pathlib import Path
from datetime import datetime

DB = Path("opsmate.db")

def conn():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, region TEXT, doc_type TEXT, version TEXT,
            uploaded_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS chunks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER, chunk_index INTEGER, text TEXT,
            embedding TEXT, page_ref TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        );
        CREATE TABLE IF NOT EXISTS questions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT, user_name TEXT, region TEXT, question TEXT,
            normalized_topic TEXT, answer TEXT, confidence TEXT,
            answered INTEGER, source_names TEXT, feedback TEXT
        );
        """)
        c.commit()

def add_document(name, region, doc_type, version):
    with conn() as c:
        cur=c.execute("INSERT INTO documents(name,region,doc_type,version,uploaded_at) VALUES(?,?,?,?,?)",
                      (name,region,doc_type,version,datetime.utcnow().isoformat()))
        c.commit()
        return cur.lastrowid

def add_chunk(document_id, idx, text, embedding, page_ref=""):
    with conn() as c:
        c.execute("INSERT INTO chunks(document_id,chunk_index,text,embedding,page_ref) VALUES(?,?,?,?,?)",
                  (document_id,idx,text,json.dumps(embedding),page_ref))
        c.commit()

def list_documents():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")]

def all_candidate_chunks(region):
    with conn() as c:
        rows=c.execute("""
        SELECT c.*, d.name, d.region, d.doc_type, d.version
        FROM chunks c JOIN documents d ON c.document_id=d.id
        WHERE d.active=1 AND (d.region=? OR d.region='Global')
        """,(region,)).fetchall()
        return [dict(r) for r in rows]

def log_question(user_name, region, question, topic, answer, confidence, answered, sources):
    with conn() as c:
        cur=c.execute("""INSERT INTO questions
        (created_at,user_name,region,question,normalized_topic,answer,confidence,answered,source_names)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (datetime.utcnow().isoformat(),user_name,region,question,topic,answer,confidence,int(answered),json.dumps(sources)))
        c.commit()
        return cur.lastrowid

def set_feedback(qid, feedback):
    with conn() as c:
        c.execute("UPDATE questions SET feedback=? WHERE id=?",(feedback,qid))
        c.commit()

def questions_df():
    import pandas as pd
    with conn() as c:
        return pd.read_sql_query("SELECT * FROM questions ORDER BY created_at DESC", c)
