from io import BytesIO
from pathlib import Path
import pandas as pd
from pypdf import PdfReader
from docx import Document

def extract(uploaded_file):
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()
    out=[]
    if name.endswith(".pdf"):
        reader=PdfReader(BytesIO(data))
        for i,p in enumerate(reader.pages):
            text=(p.extract_text() or "").strip()
            if text: out.append((text, f"Page {i+1}"))
    elif name.endswith(".docx"):
        d=Document(BytesIO(data))
        text="\n".join(p.text for p in d.paragraphs if p.text.strip())
        out.append((text,"Document"))
    elif name.endswith(".xlsx"):
        xls=pd.ExcelFile(BytesIO(data))
        for sheet in xls.sheet_names:
            df=pd.read_excel(BytesIO(data), sheet_name=sheet)
            out.append((df.fillna("").astype(str).to_csv(index=False), f"Sheet: {sheet}"))
    elif name.endswith(".csv"):
        out.append((pd.read_csv(BytesIO(data)).fillna("").astype(str).to_csv(index=False),"CSV"))
    elif name.endswith(".txt"):
        out.append((data.decode("utf-8", errors="ignore"),"Text"))
    else:
        raise ValueError("Unsupported file type")
    return out

def chunk_text(text, size=1400, overlap=220):
    text=" ".join(text.split())
    if not text: return []
    chunks=[]
    start=0
    while start < len(text):
        end=min(len(text), start+size)
        chunks.append(text[start:end])
        if end==len(text): break
        start=max(0,end-overlap)
    return chunks
