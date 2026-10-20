from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from huggingface_hub import login
from langchain_ollama import ChatOllama


load_dotenv()
persistent_directory = "db/class_db"

# Load embeddings and vector store
embedding_model = HuggingFaceEmbeddings(model_name="BAAI/bge-m3", encode_kwargs={"normalize_embeddings": True})

db = Chroma(
    persist_directory=persistent_directory,
    embedding_function=embedding_model,
    collection_metadata={"hnsw:space": "cosine"}  
)

# Search for relevant documents
query = input('How may I assist you: ')

retriever = db.as_retriever(search_kwargs={"k": 5})

# retriever = db.as_retriever(
#     search_type="similarity_score_threshold",
#     search_kwargs={
#         "k": 5,
#         "score_threshold": 0.3  # Only return chunks with cosine similarity ≥ 0.3
#     }
# )

relevant_docs = retriever.invoke(query)


# Display results
print("--- Context ---")
for i, doc in enumerate(relevant_docs, 1):
    print(f"Document {i}:\n{doc.page_content}\n")


# Combine the query and the relevant document contents
combined_input = f"""
The user's request is:

{query}


Based on the chunks provided below use that to answer the questions of the user. For questions you dont have enough context, knowledge for say you dont have enough information to answer it do not assume anything, everything should be factual.

Requirements:
1. Use ONLY information found in the documents.
2. Do not invent facts or information.
5. Make the incorrect options plausible but clearly incorrect based
   on the provided documents.
7. Cover different parts of the provided documents.
10. Return ONLY valid response.

Document chunks:

{chr(10).join([f"- {doc.page_content}" for doc in relevant_docs])}
"""
# Create a ChatOllama model

model = ChatOllama(
    model="qwen2.5:3b",
    temperature= 0
)


# Define the messages for the model
messages = [
    SystemMessage(content=
                  "You are a helpful assistant, your job is help out the user by answering the user questions in the most accurate way possible"),
    HumanMessage(content=combined_input),
]

# Invoke the model with the combined input
result = model.invoke(messages)

# Display the full result and content only
print("\n--- Generated Response ---")
# print("Full result:")
# print(result)
print("Content only:")
print(result.content)