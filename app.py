from flask import Flask, render_template, request, session
from groq import Groq
import os
import uuid
import PyPDF2
from docx import Document


app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

# Maximum uploaded file size = 10 MB
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
Do not pretend that information is present in the notes if it
is not actually present.
"""


def extract_pdf_text(file_path):

    text = ""

    with open(file_path, "rb") as file:

        reader = PyPDF2.PdfReader(file)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    return text


def extract_docx_text(file_path):

    document = Document(file_path)

    text = ""

    for paragraph in document.paragraphs:

        if paragraph.text.strip():
            text += paragraph.text + "\n"

    return text


def extract_text(file_path, extension):

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    if extension == ".docx":
        return extract_docx_text(file_path)

    return ""


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

    unique_name = str(uuid.uuid4()) + extension

    file_path = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    try:

        file.save(file_path)

        extracted_text = extract_text(
            file_path,
            extension
        )

        if not extracted_text.strip():

            if os.path.exists(file_path):
                os.remove(file_path)

            return render_template(
                "index.html",
                answer=(
                    "I could not extract readable text from this file."
                ),
                uploaded_file=None
            )

        # Save document information
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
                "Study material uploaded successfully. "
                "You can now ask questions about your notes."
            ),
            uploaded_file=file.filename
        )

    except Exception as error:

        print("Upload Error:", error)

        if os.path.exists(file_path):
            os.remove(file_path)

        return render_template(
            "index.html",
            answer="There was a problem processing your file.",
            uploaded_file=None
        )


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
            answer="Please enter a question.",
            question="",
            selected_mode=study_mode,
            uploaded_file=session.get("uploaded_file")
        )


    # Mode-specific instructions

    if study_mode == "explain":

        instruction = """
EXPLAIN MODE

Explain the requested topic clearly.

Use:
- Simple language
- Headings
- Bullet points
- Examples when useful

If study material is uploaded, explain the topic mainly
using the uploaded material.
"""


    elif study_mode == "summarize":

        instruction = """
SUMMARIZE MODE

Summarize the uploaded study material or requested topic.

Focus on:
- Important concepts
- Definitions
- Key points
- Important examples

Use headings and bullet points.

Keep the summary easy for a student to revise.
"""


    elif study_mode == "quiz":

        instruction = """
QUIZ MODE

Create a quiz based mainly on the uploaded study material.

Create:
- 5 multiple-choice questions
- 5 short-answer questions

Then provide an answer key.

Do not add unrelated topics that are not present
in the uploaded material.
"""


    elif study_mode == "doubt":

        instruction = """
DOUBT MODE

Answer the student's doubt step by step.

Use the uploaded study material as the main source
when the question relates to it.

Explain difficult parts in simple language.
"""


    else:

        instruction = """
Answer the student's question clearly and educationally.
"""


    # Get conversation
    conversation = session.get(
        "conversation",
        [
            {
                "role": "system",
                "content": system_instruction
            }
        ]
    )


    # Get notes
    document_text = session.get(
        "document_text",
        ""
    )


    # Limit notes sent to AI
    maximum_chars = 50000

    if document_text:

        notes = document_text[:maximum_chars]

        notes_context = f"""
UPLOADED STUDY MATERIAL

Use the following material as the primary source.

----- START NOTES -----

{notes}

----- END NOTES -----

IMPORTANT:
If the student's question cannot be answered from these notes,
say that the information is not available in the uploaded material.
"""


    else:

        notes_context = """
No study material has been uploaded.

Answer the student's question normally.
"""


    # Add instructions
    conversation.append(
        {
            "role": "system",
            "content": instruction
        }
    )

    conversation.append(
        {
            "role": "system",
            "content": notes_context
        }
    )


    # Add question
    conversation.append(
        {
            "role": "user",
            "content": user_question
        }
    )


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


    # Save conversation
    conversation.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    session["conversation"] = conversation
    session.modified = True


    return render_template(
        "index.html",
        question=user_question,
        answer=answer,
        selected_mode=study_mode,
        uploaded_file=session.get("uploaded_file")
    )


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

            print("Delete Error:", error)


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


@app.errorhandler(413)
def file_too_large(error):

    return render_template(
        "index.html",
        answer="File is too large. Maximum allowed size is 10 MB.",
        uploaded_file=session.get("uploaded_file")
    ), 413


if __name__ == "__main__":

    app.run(debug=True)
