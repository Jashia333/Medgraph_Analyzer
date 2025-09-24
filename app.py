import os
import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_neo4j import Neo4jGraph   # ✅ new import
from pdf_processor import process_pdf

# -------------------------
# Load defaults from .env
# -------------------------
load_dotenv()

default_llm_api_key = os.getenv("GEMINI_API_KEY", "")
default_neo4j_url = os.getenv("NEO4J_URI", "")
default_neo4j_user = os.getenv("NEO4J_USERNAME", "03b75dbd")  # ✅ corrected key
default_neo4j_password = os.getenv("NEO4J_PASSWORD", "")
default_neo4j_database = os.getenv("NEO4J_DATABASE", "03b75dbd")

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="Medgraph Analyzer", page_icon="💊")
st.title("💊 Medgraph Analyzer")

st.sidebar.header("⚙️ Configuration")

# Input fields
llm_api_key = st.sidebar.text_input("Gemini API Key", value=default_llm_api_key, type="password")
neo4j_url = st.sidebar.text_input("Neo4j URL", value=default_neo4j_url)
neo4j_user = st.sidebar.text_input("Neo4j User", value=default_neo4j_user)
neo4j_password = st.sidebar.text_input("Neo4j Password", value=default_neo4j_password, type="password")
neo4j_database = st.sidebar.text_input("Neo4j Database", value=default_neo4j_database)

# -------------------------
# Save & Connect
# -------------------------
if st.sidebar.button("Save and connect"):

    if not llm_api_key or not neo4j_url or not neo4j_user or not neo4j_password or not neo4j_database:
        st.sidebar.error("❌ Please fill in all fields.")
    else:
        # Store in session
        st.session_state["api_key"] = llm_api_key
        st.session_state["NEO4J_URL"] = neo4j_url
        st.session_state["NEO4J_USER"] = neo4j_user
        st.session_state["NEO4J_PASSWORD"] = neo4j_password
        st.session_state["NEO4J_DATABASE"] = neo4j_database

        # Init models
        llm = ChatGoogleGenerativeAI(
            google_api_key=llm_api_key,
            model="gemini-1.5-flash",
            temperature=0.2
        )
        embeddings = GoogleGenerativeAIEmbeddings(
            google_api_key=llm_api_key,
            model="models/embedding-001"
        )

        st.session_state["llm"] = llm
        st.session_state["embeddings"] = embeddings

        # Connect Neo4j
        try:
            graph = Neo4jGraph(
                url=neo4j_url,
                username=neo4j_user,
                password=neo4j_password,
                database=neo4j_database   # ✅ required for Aura
            )
            st.session_state["graph"] = graph
            st.sidebar.success("✅ Configuration saved and connected successfully!")
            st.write("🔐 Connected to Neo4j and Gemini Flash!")
        except Exception as e:
            st.error(f"❌ Failed to connect to Neo4j: {e}")

# -------------------------
# Test Gemini
# -------------------------
if "llm" in st.session_state:
    st.subheader("🤖 Test Gemini Flash")
    test_prompt = st.text_input("Enter a test prompt for Gemini Flash:")
    if st.button("Test Gemini Flash"):
        with st.spinner("Getting response from Gemini Flash..."):
            response = st.session_state["llm"].predict(test_prompt)
            st.write("Response from Gemini Flash:")
            st.write(response)

# -------------------------
# File Upload & Process
# -------------------------
if "llm" in st.session_state and "graph" in st.session_state:
    st.subheader("📂 Upload and Process Medical PDF")
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

    if uploaded_file:
        process_pdf(
            uploaded_file,
            st.session_state["llm"],
            st.session_state["embeddings"],
            st.session_state["graph"],
            st.session_state["NEO4J_URL"],
            st.session_state["NEO4J_USER"],
            st.session_state["NEO4J_PASSWORD"]
        )

# -------------------------
# Q&A Interface
# -------------------------
if "qa" in st.session_state:
    st.subheader("💬 Ask Questions about the Medical Graph")
    user_question = st.text_input("Enter your question:")
    if st.button("Ask"):
        with st.spinner("Querying Neo4j..."):
            result = st.session_state["qa"].invoke({"query": user_question})
            st.write("**Answer:**")
            st.write(result["result"])
