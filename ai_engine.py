import base64, json, math, re
import numpy as np
from openai import OpenAI
from db import all_candidate_chunks

FALLBACK = "Please consult with your supervisor. I don't have a reliable answer to this question in the approved knowledge available to me now."

AUTHORITY = {
    ("regional","SOP"): 100, ("global","SOP"): 90,
    ("regional","FAQ"): 80, ("global","FAQ"): 70,
    ("regional","Quality Error"): 65, ("global","Quality Error"): 60,
    ("regional","Other"): 50, ("global","Other"): 45,
}

def client(api_key):
    return OpenAI(api_key=api_key)

def embed_texts(api_key, texts):
    c=client(api_key)
    r=c.embeddings.create(model="text-embedding-3-small", input=texts)
    return [x.embedding for x in r.data]

def cosine(a,b):
    a=np.array(a,dtype=float); b=np.array(b,dtype=float)
    den=np.linalg.norm(a)*np.linalg.norm(b)
    return float(np.dot(a,b)/den) if den else 0.0

def retrieve(api_key, question, region, k=8):
    qemb=embed_texts(api_key,[question])[0]
    rows=all_candidate_chunks(region)
    scored=[]
    for r in rows:
        emb=json.loads(r["embedding"])
        sim=cosine(qemb,emb)
        scope="regional" if r["region"]==region else "global"
        authority=AUTHORITY.get((scope,r["doc_type"]),40)
        # Similarity dominates; authority resolves close evidence.
        score=sim + authority/1000.0
        r["similarity"]=sim; r["authority"]=authority; r["score"]=score
        scored.append(r)
    return sorted(scored,key=lambda x:x["score"],reverse=True)[:k]

def image_context(api_key, uploaded_image, question):
    if uploaded_image is None: return ""
    raw=uploaded_image.getvalue()
    mime=uploaded_image.type or "image/png"
    b64=base64.b64encode(raw).decode()
    c=client(api_key)
    resp=c.responses.create(
        model="gpt-4o-mini",
        input=[{"role":"user","content":[
            {"type":"input_text","text":f"""Read this operations screenshot carefully.
Describe only visible information relevant to answering this user's question:
{question}
Capture error text, status, codes and fields. Do not invent hidden details."""},
            {"type":"input_image","image_url":f"data:{mime};base64,{b64}"}
        ]}]
    )
    return resp.output_text

def answer(api_key, question, region, image=None):
    img = image_context(api_key,image,question) if image else ""
    search_question = question + ("\nScreenshot context: "+img if img else "")
    hits=retrieve(api_key,search_question,region)
    # Conservative evidence gate.
    if not hits or hits[0]["similarity"] < 0.30:
        return {"answer":FALLBACK,"confidence":"Low","answered":False,"topic":"Unresolved","sources":[]}

    evidence=[]
    for i,h in enumerate(hits,1):
        evidence.append(
            f"[SOURCE {i}] name={h['name']} | region={h['region']} | type={h['doc_type']} | "
            f"version={h['version']} | ref={h['page_ref']} | authority={h['authority']}\n{h['text']}"
        )

    prompt=f"""
You are OpsMate, an internal operations knowledge assistant.

USER REGION: {region}
USER QUESTION: {question}
SCREENSHOT CONTEXT: {img or "None"}

APPROVED EVIDENCE:
{chr(10).join(evidence)}

MANDATORY DECISION RULES:
1. Answer ONLY from APPROVED EVIDENCE. Never use general travel/GDS knowledge to fill a gap.
2. Give ONE clear operational answer, not a menu of competing possibilities.
3. Prefer the highest-authority current regional SOP. Global documents apply to every region.
4. If two high-authority sources materially conflict, DO NOT choose. Return the fallback exactly.
5. If evidence does not directly support the requested action, return the fallback exactly.
6. Understand spelling mistakes and Romanized Hindi/Kannada/Telugu, but write the final operational answer in simple English.
7. Never invent commands, fees, time limits, approvals, fare rules or policy.
8. Keep the answer concise and action-oriented.
9. Cite sources using [1], [2] corresponding to the evidence list.
10. If screenshot context exists, explain visible error/context only when supported by evidence.

FALLBACK:
{FALLBACK}

Return valid JSON only:
{{
 "decision":"a one-sentence direct answer or the fallback",
 "steps":["step 1","step 2"],
 "important":"optional caution or empty string",
 "source_ids":[1,2],
 "confidence":"High|Medium|Low",
 "topic":"short normalized topic",
 "escalate":false
}}
If fallback is required, set steps=[], source_ids=[], confidence="Low", escalate=true.
"""
    c=client(api_key)
    resp=c.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        temperature=0
    )
    txt=resp.output_text.strip()
    txt=re.sub(r"^```json\s*|\s*```$","",txt,flags=re.I|re.S)
    try:
        data=json.loads(txt)
    except Exception:
        return {"answer":FALLBACK,"confidence":"Low","answered":False,"topic":"Unresolved","sources":[]}

    if data.get("escalate") or data.get("decision")==FALLBACK:
        return {"answer":FALLBACK,"confidence":"Low","answered":False,"topic":data.get("topic","Unresolved"),"sources":[]}

    ids=[x for x in data.get("source_ids",[]) if isinstance(x,int) and 1<=x<=len(hits)]
    sources=[]
    for i in ids[:3]:
        h=hits[i-1]
        sources.append({"name":h["name"],"ref":h["page_ref"],"region":h["region"],"type":h["doc_type"]})
    answer_text=data.get("decision","")
    steps=data.get("steps",[])
    if steps:
        answer_text += "\n\n**What to do**\n" + "\n".join(f"{i+1}. {s}" for i,s in enumerate(steps))
    if data.get("important"):
        answer_text += "\n\n**Important:** " + data["important"]
    return {
        "answer":answer_text,
        "confidence":data.get("confidence","Medium"),
        "answered":True,
        "topic":data.get("topic","Other"),
        "sources":sources
    }
