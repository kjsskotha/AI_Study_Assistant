from flask import Flask, render_template, request, session
from groq import Groq
import os
import uuid
import PyPDF2
from docx import Document


app = Flask(__name__)


# Flask secret key
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)


# Maximum upload size: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# Groq API
api_key = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=api_key)


# Upload folder
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Main AI instructions
system_instruction = """
You are an AI Study Assistant for students.

Your job is to help students learn from their study material
and understand difficult subjects.

LANGUAGE RULES:
1. Understand questions written in any language.
2. Reply in the same language as the student's question.
3. If the student asks for another language, use that language.
4. Do not unnecessarily translate the question.

STUDY RULES:
1. Explain concepts clearly and simply.
2. Break difficult topics into smaller parts.
3. Use headings and bullet points.
4. Use examples when useful.
5. Be educational and easy to understand.
6. Remember previous messages in the conversation.

NOTES RULE:
If study material has been uploaded, use that material as
the main source for questions about the uploaded material.

Do not pretend information is present in the notes if it
is not actually present.
"""


# --------------------------------------------------
# PDF TEXT EXTRACTION
# --------------------------------------------------

def extract_pdf_text(file_path):

    text = ""

    with open(file_path, "rb") as file:

        reader = PyPDF2.PdfReader(file)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:

                text += page_text + "\n"

    return text


# --------------------------------------------------
# DOCX TEXT EXTRACTION
# --------------------------------------------------

def extract_docx_text(file_path):

    document = Document(file_path)

    text = ""

    for paragraph in document.paragraphs:

        if paragraph.text.strip():

            text += paragraph.text + "\n"

    return text


# --------------------------------------------------
# SELECT EXTRACTION METHOD
# --------------------------------------------------

def extract_text(file_path, extension):

    if extension == ".pdf":

        return extract_pdf_text(file_path)

    elif extension == ".docx":

        return extract_docx_text(file_path)

    return ""


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():

    if "conversation" not in session:

        session["conversation"] = [
            {
                "role": "system",
                "content": system_instruction
            }
        ]

    return render_template(
        "index.html",
        answer=None,
        uploaded_file=session.get("uploaded_file")
    )


# --------------------------------------------------
# UPLOAD STUDY MATERIAL
# --------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():

    file = request.files.get("study_file")

    if not file or file.filename == "":

        return render_template(
            "index.html",
            answer="Please select a PDF or DOCX file.",
            uploaded_file=None
        )


    filename = file.filename.lower()


    # Check file type

    if filename.endswith(".pdf"):

        extension = ".pdf"

    elif filename.endswith(".docx"):

        extension = ".docx"

    else:

        return render_template(
            "index.html",
            answer="Only PDF and DOCX files are supported.",
            uploaded_file=None
        )


    # Unique file name

    unique_name = str(uuid.uuid4()) + extension

    file_path = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )


    try:

        # Save file

        file.save(file_path)


        # Extract text

        extracted_text = extract_text(
            file_path,
            extension
        )


        # Check text

        if not extracted_text.strip():

            os.remove(file_path)

            return render_template(
                "index.html",
                answer=(
                    "I could not extract readable text from this file. "
                    "Please try a text-based PDF or DOCX file."
                ),
                uploaded_file=None
            )


        # Save information

        session["uploaded_file"] = file.filename

        session["uploaded_path"] = file_path

        session["document_text"] = extracted_text


        # Start fresh conversation

        session["conversation"] = [

            {
                "role": "system",
                "content": system_instruction
            }

        ]

        session.modified = True


        return render_template(
            "index.html",
            answer=(
                "Your study material was uploaded successfully. "
                "You can now ask questions about it."
            ),
            uploaded_file=file.filename
        )


    except Exception as error:

        print("File Error:", error)


        if os.path.exists(file_path):

            os.remove(file_path)


        return render_template(
            "index.html",
            answer=(
                "There was a problem processing the file. "
                "Please try another file."
            ),
            uploaded_file=None
        )


# --------------------------------------------------
# ASK AI
# --------------------------------------------------

@app.route("/ask", methods=["POST"])
def ask():

    user_question = request.form.get(
        "question",
        ""
    ).strip()


    study_mode = request.form.get(
        "mode",
        "explain"
    )


    if not user_question:

        return render_template(
            "index.html",
            answer="Please enter a question or topic.",
            question="",
            selected_mode=study_mode,
            uploaded_file=session.get("uploaded_file")
        )


    # --------------------------------------------------
    # STUDY MODE INSTRUCTIONS
    # --------------------------------------------------

    if study_mode == "explain":

        instruction = """
Explain the topic clearly for a student.

Reply in the same language as the student's question.

Use:
- Simple language
- Clear headings
- Bullet points
- Examples when useful

If study material is uploaded, use it as the main source.
"""


    elif study_mode == "summarize":

        instruction = """
Summarize the uploaded study material or given topic.

Reply in the same language as the student's question.

Include:
- Important concepts
- Important definitions
- Key points
- Important examples

Use headings and bullet points.

Keep the summary easy to revise.
"""


    elif study_mode == "quiz":

        instruction = """
Create a quiz about the given topic.

Reply in the same language as the student's question.

Create:
- 5 multiple-choice questions
- 5 short-answer questions

Provide an answer key separately.

If study material is uploaded,
create the questions mainly from that material.
"""


    elif study_mode == "doubt":

        instruction = """
Answer the student's doubt clearly.

Reply in the same language as the student's question.

Explain the concept step by step.

Use a simple example when useful.

If study material is uploaded,
use it as the main source.
"""


    elif study_mode == "notes":

        instruction = """
The student wants to study from their uploaded notes.

Reply in the same language as the student's question.

Use the uploaded study material as the MAIN SOURCE.

If the student asks:

"Generate important exam questions"

or similar, create useful exam-oriented questions
based ONLY on the uploaded study material.

Organize them clearly into:

1. Very Short Answer Questions
2. Short Answer Questions
3. Long Answer Questions

If suitable, also include important definitions,
concepts and topics that students should revise.

Do not invent topics that are not present in the
uploaded study material.

If something is not available in the notes,
clearly say that it is not found in the uploaded material.
"""


    else:

        instruction = """
Help the student understand the topic clearly.

Reply in the same language as the student's question.
"""


    # --------------------------------------------------
    # GET CONVERSATION
    # --------------------------------------------------

    conversation = session.get(
        "conversation",
        [
            {
                "role": "system",
                "content": system_instruction
            }
        ]
    )


    # --------------------------------------------------
    # GET UPLOADED NOTES
    # --------------------------------------------------

    document_text = session.get(
        "document_text",
        ""
    )


    # Maximum notes sent to AI

    maximum_document_chars = 50000


    if document_text:

        document_for_ai = document_text[
            :maximum_document_chars
        ]


        notes_instruction = f"""
The student has uploaded study material.

Use this material as the main source.

Do not claim that information is in the material
if it is not actually present.

----- BEGIN STUDY MATERIAL -----

{document_for_ai}

----- END STUDY MATERIAL -----
"""


    else:

        notes_instruction = """
No study material has been uploaded.

Answer normally.

If the student selected "Ask from My Notes",
tell them that they need to upload study material first.
"""


    # --------------------------------------------------
    # ADD INSTRUCTIONS
    # --------------------------------------------------

    conversation.append(
        {
            "role": "system",
            "content": instruction
        }
    )


    conversation.append(
        {
            "role": "system",
            "content": notes_instruction
        }
    )


    # Add question

    conversation.append(
        {
            "role": "user",
            "content": user_question
        }
    )


    # --------------------------------------------------
    # SEND TO GROQ
    # --------------------------------------------------

    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-20b",

            messages=conversation

        )


        answer = response.choices[0].message.content


    except Exception as error:

        print("Groq Error:", error)


        answer = (
            "Sorry, I could not generate a response right now. "
            "Please try again."
        )


    # --------------------------------------------------
    # SAVE CONVERSATION
    # --------------------------------------------------

    conversation.append(
        {
            "role": "assistant",
            "content": answer
        }
    )


    session["conversation"] = conversation

    session.modified = True


    # --------------------------------------------------
    # DISPLAY ANSWER
    # --------------------------------------------------

    return render_template(

        "index.html",

        question=user_question,

        answer=answer,

        selected_mode=study_mode,

        uploaded_file=session.get("uploaded_file")

    )


# --------------------------------------------------
# CLEAR CONVERSATION
# --------------------------------------------------

@app.route("/clear")
def clear():

    uploaded_path = session.get(
        "uploaded_path"
    )


    if uploaded_path:

        try:

            if os.path.exists(uploaded_path):

                os.remove(uploaded_path)

        except Exception as error:

            print("File Delete Error:", error)


    session.clear()


    session["conversation"] = [

        {
            "role": "system",
            "content": system_instruction
        }

    ]

    session.modified = True


    return render_template(
        "index.html",
        answer=None,
        uploaded_file=None
    )


# --------------------------------------------------
# FILE TOO LARGE
# --------------------------------------------------

@app.errorhandler(413)
def file_too_large(error):

    return render_template(

        "index.html",

        answer=(
            "File is too large. "
            "Maximum allowed size is 10 MB."
        ),

        uploaded_file=session.get(
            "uploaded_file"
        )

    ), 413


# --------------------------------------------------
# RUN APP
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True
    )
