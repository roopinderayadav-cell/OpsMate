import io, json, time
import streamlit as st
import pandas as pd
from db import init_db, add_document, add_chunk, list_documents, log_question, set_feedback, questions_df
from ingest import extract, chunk_text
from ai_engine import embed_texts, answer, FALLBACK

st.set_page_config(page_title="OpsMate", page_icon="✈️", layout="wide")
init_db()

st.markdown("""
<style>
.block-container{padding-top:1.3rem;max-width:1500px}
.ops-title{font-size:2.35rem;font-weight:800;color:#10233F;margin-bottom:.1rem}
.ops-sub{color:#66758a;margin-bottom:1rem}
.answerbox{border:1px solid #dce6f3;border-radius:16px;padding:20px;background:#fff}
.small{font-size:.85rem;color:#6b7a90}
div[data-testid="stMetric"]{border:1px solid #e4eaf2;padding:12px;border-radius:14px;background:white}
</style>
""", unsafe_allow_html=True)

def secret(name, default=""):
    try: return st.secrets[name]
    except Exception: return default

api_key=secret("OPENAI_API_KEY")
admin_password=secret("ADMIN_PASSWORD","admin")

if "role" not in st.session_state: st.session_state.role="Agent"
if "name" not in st.session_state: st.session_state.name=""
if "region" not in st.session_state: st.session_state.region="NORAM"
if "last_qid" not in st.session_state: st.session_state.last_qid=None
if "last_result" not in st.session_state: st.session_state.last_result=None

with st.sidebar:
    st.markdown("## ✈️ OpsMate")
    st.caption("Your AI Operations Companion")
    st.session_state.name=st.text_input("Name / Employee ID", value=st.session_state.name, placeholder="e.g. Amit / E12345")
    st.session_state.region=st.radio("Region",["NORAM","Europe","APAC"], index=["NORAM","Europe","APAC"].index(st.session_state.region))
    role=st.radio("Mode",["Agent","Admin"], horizontal=True)
    if role=="Admin":
        pw=st.text_input("Admin password",type="password")
        if pw==admin_password:
            st.session_state.role="Admin"
        else:
            st.session_state.role="Agent"
            if pw: st.error("Incorrect admin password")
    else: st.session_state.role="Agent"
    st.divider()
    page_options=["Ask OpsMate","My Questions","Knowledge Library"]
    if st.session_state.role=="Admin":
        page_options += ["Upload Documents","Dashboard"]
    page=st.radio("Navigate",page_options,label_visibility="collapsed")
    st.divider()
    st.caption("If OpsMate cannot find reliable approved guidance, it will ask you to consult your supervisor.")

st.markdown('<div class="ops-title">OpsMate</div>',unsafe_allow_html=True)
st.markdown('<div class="ops-sub">Ask. Resolve. Learn. — Region-aware process and product knowledge.</div>',unsafe_allow_html=True)

if not api_key:
    st.error("OPENAI_API_KEY is missing. Add it in .streamlit/secrets.toml locally or Streamlit Cloud Secrets.")
    st.stop()

if page=="Ask OpsMate":
    st.subheader(f"How can OpsMate help you today? · {st.session_state.region}")
    chips=["Ticketing","Refunds","Exchanges","OBT","Invoicing","Profiles","Fare Rules","GDS","Travel Policy","Quality / Errors"]
    st.caption("Common areas: " + " · ".join(chips))
    q=st.text_area("Your question",height=110,placeholder="Ask in English or Romanized Hindi/Kannada/Telugu. Spelling mistakes are okay.")
    image=st.file_uploader("Optional screenshot",type=["png","jpg","jpeg","webp"])
    if st.button("Ask OpsMate ✈️",type="primary",use_container_width=True):
        if not st.session_state.name.strip():
            st.warning("Please enter your name / employee ID in the sidebar.")
        elif not q.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Checking approved knowledge and deciding the best supported answer..."):
                result=answer(api_key,q.strip(),st.session_state.region,image)
                qid=log_question(st.session_state.name,st.session_state.region,q.strip(),result["topic"],
                                 result["answer"],result["confidence"],result["answered"],
                                 [s["name"] for s in result["sources"]])
                st.session_state.last_qid=qid
                st.session_state.last_result=result
    r=st.session_state.last_result
    if r:
        if r["answered"]:
            st.success(r["answer"])
            st.write(f"**Confidence:** {r['confidence']}")
            if r["sources"]:
                with st.expander(f"Sources ({len(r['sources'])})"):
                    for s in r["sources"]:
                        st.write(f"📄 **{s['name']}** · {s['region']} · {s['type']} · {s['ref']}")
        else:
            st.warning(r["answer"])
        c1,c2,_=st.columns([1,1,5])
        if c1.button("👍 Helpful"):
            set_feedback(st.session_state.last_qid,"Helpful"); st.toast("Feedback saved")
        if c2.button("👎 Not helpful"):
            set_feedback(st.session_state.last_qid,"Not Helpful"); st.toast("Feedback saved")

elif page=="Knowledge Library":
    docs=pd.DataFrame(list_documents())
    st.subheader("Knowledge Library")
    if docs.empty: st.info("No documents uploaded yet.")
    else:
        show=docs[["name","region","doc_type","version","uploaded_at","active"]].copy()
        st.dataframe(show,use_container_width=True,hide_index=True)

elif page=="My Questions":
    st.subheader("My Questions")
    df=questions_df()
    if st.session_state.name:
        df=df[df["user_name"]==st.session_state.name]
    if df.empty: st.info("No questions yet.")
    else:
        st.dataframe(df[["created_at","region","question","normalized_topic","confidence","feedback"]],use_container_width=True,hide_index=True)

elif page=="Upload Documents":
    st.subheader("Admin · Upload Documents")
    st.info("Upload approved knowledge only. Global documents are searched for all regions.")
    c1,c2,c3=st.columns(3)
    region=c1.selectbox("Region",["NORAM","Europe","APAC","Global"])
    doc_type=c2.selectbox("Document type",["SOP","FAQ","Quality Error","Other"])
    version=c3.text_input("Version",value="1.0")
    ups=st.file_uploader("Documents",type=["pdf","docx","xlsx","csv","txt"],accept_multiple_files=True)
    if st.button("Upload and index",type="primary"):
        if not ups: st.warning("Choose at least one document.")
        else:
            prog=st.progress(0)
            for n,u in enumerate(ups):
                try:
                    sections=extract(u)
                    doc_id=add_document(u.name,region,doc_type,version)
                    all_chunks=[]
                    refs=[]
                    for text,ref in sections:
                        cs=chunk_text(text)
                        all_chunks.extend(cs); refs.extend([ref]*len(cs))
                    if not all_chunks: raise ValueError("No readable text found.")
                    embs=[]
                    batch=64
                    for i in range(0,len(all_chunks),batch):
                        embs.extend(embed_texts(api_key,all_chunks[i:i+batch]))
                    for i,(txt,emb,ref) in enumerate(zip(all_chunks,embs,refs)):
                        add_chunk(doc_id,i,txt,emb,ref)
                    st.success(f"Indexed {u.name} · {len(all_chunks)} knowledge chunks")
                except Exception as e:
                    st.error(f"{u.name}: {e}")
                prog.progress((n+1)/len(ups))

elif page=="Dashboard":
    st.subheader("Admin · Dashboard & Analytics")
    df=questions_df()
    if df.empty:
        st.info("Analytics will appear after agents start asking questions.")
    else:
        df["created_at"]=pd.to_datetime(df["created_at"],errors="coerce")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Total Questions",len(df))
        c2.metric("Answered",f"{df['answered'].mean()*100:.0f}%")
        rated=df[df["feedback"].notna()]
        helpful=(rated["feedback"].eq("Helpful").mean()*100) if len(rated) else 0
        c3.metric("Helpful",f"{helpful:.0f}%")
        c4.metric("Unanswered",int((df["answered"]==0).sum()))
        a,b=st.columns(2)
        with a:
            st.markdown("#### Questions by Region")
            st.bar_chart(df["region"].value_counts())
        with b:
            st.markdown("#### Top Topics")
            st.bar_chart(df["normalized_topic"].value_counts().head(10))
        st.markdown("#### Most Common Questions")
        common=df.groupby(["question","region"]).size().reset_index(name="count").sort_values("count",ascending=False).head(15)
        st.dataframe(common,use_container_width=True,hide_index=True)
        st.markdown("#### Unanswered / Needs Review")
        unresolved=df[df["answered"]==0][["created_at","region","user_name","question","normalized_topic"]]
        st.dataframe(unresolved,use_container_width=True,hide_index=True)
        st.markdown("#### Feedback Detail")
        st.dataframe(df[["created_at","region","user_name","question","normalized_topic","confidence","feedback"]],use_container_width=True,hide_index=True)
        out=io.BytesIO()
        with pd.ExcelWriter(out,engine="openpyxl") as writer:
            df.to_excel(writer,index=False,sheet_name="All Questions")
            common.to_excel(writer,index=False,sheet_name="Common Questions")
            unresolved.to_excel(writer,index=False,sheet_name="Unresolved")
        st.download_button("⬇️ Export to Excel",out.getvalue(),"opsmate_analytics.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
