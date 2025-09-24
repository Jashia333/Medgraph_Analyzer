import tempfile
import streamlit as st

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import Neo4jVector
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain


def process_pdf(uploaded_file, llm, embeddings, graph,
                neo4j_url, neo4j_username, neo4j_password, neo4j_database):
    """
    Process an uploaded medical PDF into the Neo4j graph.
    Creates nodes, relationships, embeddings, and sets up a Cypher QA chain.
    """

    with st.spinner("⏳ Processing the PDF..."):
        # Save PDF temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_file.read())
            tmp_file_path = tmp_file.name

        # Load and split text
        loader = PyPDFLoader(tmp_file_path)
        pages = loader.load_and_split()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=40)
        docs = text_splitter.split_documents(pages)

        lc_docs = [
            Document(
                page_content=doc.page_content.replace("\n", ""),
                metadata={'source': uploaded_file.name}
            )
            for doc in docs
        ]

        # Clear graph before new upload
        graph.query("MATCH (n) DETACH DELETE n;")

        # Define allowed medical nodes and relationships
        allowed_nodes = ["Patient", "Disease", "Medication", "Test", "Symptom", "Doctor"]
        allowed_relationships = [
            "HAS_DISEASE", "TAKES_MEDICATION",
            "UNDERWENT_TEST", "HAS_SYMPTOM", "TREATED_BY"
        ]

        # Convert text docs → graph docs
        transformer = LLMGraphTransformer(
            llm=llm,
            allowed_nodes=allowed_nodes,
            allowed_relationships=allowed_relationships,
            node_properties=False,
            relationship_properties=False
        )

        graph_documents = transformer.convert_to_graph_documents(lc_docs)
        graph.add_graph_documents(graph_documents, include_source=True)

        # Create hybrid vector index in Neo4j
        Neo4jVector.from_existing_graph(
            embedding=embeddings,
            url=neo4j_url,
            username=neo4j_username,
            password=neo4j_password,
            database=neo4j_database,   # ✅ use correct DB name
            node_label="Patient",      # Change if needed
            text_node_properties=["id", "text"],
            embedding_node_property="embedding",
            index_name="vector_index",
            keyword_index_name="entity_index",
            search_type="hybrid"
        )

        st.success(f"✅ {uploaded_file.name} processed successfully.")

        # Build schema prompt for QA
        schema = graph.get_schema

        template = """
        Task: Generate a Cypher query to fetch information from the medical graph.

        Instructions:
        - Use only relationships and properties available in schema.
        - Do not invent relationships or properties outside schema.
        - Return Cypher query only (no explanation).

        Schema:
        {schema}

        Question: {question}
        """

        question_prompt = PromptTemplate(
            template=template,
            input_variables=["schema", "question"]
        )

        qa = GraphCypherQAChain.from_llm(
            llm=llm,
            graph=graph,
            cypher_prompt=question_prompt,
            verbose=True,
            allow_dangerous_requests=True
        )

        st.session_state['qa'] = qa
