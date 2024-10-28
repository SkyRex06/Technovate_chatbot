from gradio_client import file
import numpy as np
import pandas as pd
import google.generativeai as genai
import unicodedata
from PyPDF2 import PdfReader
from typing import List
import gradio as gr
import os

# Set up the API key for Google Generative AI
genai.configure(api_key="AIzaSyAS_IupOHa9_LF5tKXKML9HnW_AFhCeKaA")

# Embedding function
def embed_fn(title, text, model='models/embedding-001', task_type="retrieval_document"):
    try:
        embedding_response = genai.embed_content(model=model, content=text, title=title, task_type=task_type)
        return embedding_response.get("embedding", None)
    except Exception as e:
        print(f"Error in embedding function: {e}")
        return None

# PDF upload and processing function
def upload_pdf_part(pdf_file):
    if pdf_file:
        pdf_reader = PdfReader(pdf_file)
        text = ""

        for page in pdf_reader.pages:
            page_text = page.extract_text() or ""
            text += page_text

        if not text.strip():
            return []  # Return an empty list if no text found

        final_text = "".join([char for char in text if unicodedata.category(char) != 'Co'])

        def get_chunks(text: str, chunk_size: int, overlap: float) -> List[str]:
            words = text.split()
            overlap_size = int(chunk_size * overlap)
            return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size - overlap_size)]

        chunks = get_chunks(final_text, chunk_size=1000, overlap=0.2)
        documents = [{"Title": chunk.split()[0] if chunk else "Untitled", "content": chunk} for chunk in chunks]
        return documents
    return []

# Retrieve best passage function
def find_best_passage(query, df):
    if df.empty:
        return "No content available for processing."
    query_embedding = genai.embed_content(model='models/embedding-001', content=query, task_type="retrieval_query")
    similarities = np.dot(np.stack(df['Embeddings'].dropna()), query_embedding["embedding"])
    best_index = np.argmax(similarities)
    return df.iloc[best_index]['content']

# Generate response prompt
def create_prompt(query, passage):
    return f"""
    You are a chatbot for Delhi Technical Campus, answering questions for students.
    QUESTION: '{query}'
    PASSAGE: '{passage.replace("'", "").replace('"', "").replace("\n", " ")}'
    ANSWER:"""

# Main chatbot function
def chatbot(query, pdf_file):
    documents = upload_pdf_part(pdf_file)
    if not documents:
        return "Please upload a valid PDF with content."

    df = pd.DataFrame(documents)
    df['Embeddings'] = df.apply(lambda row: embed_fn(row['Title'], row['content']), axis=1)

    if df['Embeddings'].isnull().all():
        return "Failed to generate embeddings for the content."

    relevant_passage = find_best_passage(query, df)
    if "No content" in relevant_passage:
        return relevant_passage

    prompt = create_prompt(query, relevant_passage)

    try:
        chat_model = genai.GenerativeModel("models/gemini-1.5-flash")
        chat = chat_model.start_chat()
        response = chat.send_message(prompt).text
        return response
    except Exception as e:
        print(f"Error in generating chat response: {e}")
        return "Failed to generate chat response."

# Define Gradio Interface
with gr.Blocks() as app:
    gr.Markdown("## Technovate Chatbot")
    pdf_input = gr.File(label="Upload your PDF here:", file_types=[".pdf"])
    user_query = gr.Textbox(label="Ask me anything related to pdf uploaded")
    chatbot_output = gr.Textbox(label="Chatbot Response", interactive=False)
    
    gr.Button("Get Response").click(fn=chatbot, inputs=[user_query, pdf_input], outputs=chatbot_output)

app.launch(share=True)


