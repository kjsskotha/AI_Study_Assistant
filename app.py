from flask import Flask, render_template, request, session
from groq import Groq
import os
import uuid
import PyPDF2
from docx import Document


app = Flask(__name__)

# Flask session secret
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

# Maximum upload size: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# Groq API
api_key = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=api_key)


# Folder for uploaded study files
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Main AI instructions
system_instruction = """
You are an AI Study Assistant for students around the world.

Your job is to help students learn and understand their subjects clearly.

LANGUAGE RULES:
1. Understand questions written in any language.
2. Reply in the same language used by the student by default.
3. If the student explicitly asks for another language, reply in that language.
4. Support English, Telugu, Hindi, Tamil, Kannada, Malayalam,
   Bengali, Marathi, Gujarati, Punjabi, Urdu and other languages.
5. Do not unnecessarily translate the student's question.

STUDY RULES:
1. Explain concepts clearly and simply.
2. Break difficult topics into smaller parts.
3. Use examples when useful.
4. Use headings, bullet points and numbered lists when appropriate.
5. Be educational, accurate and easy to understand.
6. Remember previous messages in the current conversation.
7. Understand follow-up questions using previous conversation context.

IMPORTANT:
If study notes are provided, use the uploaded notes as the main source.
Do not invent information that is not supported by the uploaded notes
when the student specifically asks about the uploaded material.
"""


def extract_pdf_text(file_path):
    """
    Extract text from a PDF file.
    """

    text = ""

    with open(file_path, "rb") as file:

        reader = PyPDF2.PdfReader(file)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

    return text


def extract_docx_text(file_path):
    """
    Extract text from a DOCX file.
    """

    document = Document(file_path)

    text = ""

    for paragraph in document.paragraphs:

        if paragraph.text.strip():
            text += paragraph.text + "\n"

    return text


def extract_text(file_path, file_extension):
    """
    Select the correct text extraction method.
    """

    if file_extension == ".pdf":

        return extract_pdf_text(file_path)

    elif file_extension == ".docx":

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

    uploaded_file = session.get("uploaded_file")

    return render_template(
        "index.html",
        answer=None,
        uploaded_file=uploaded_file
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

    # Get file extension
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

    # Create unique filename
    unique_name = str(uuid.uuid4()) + extension

    file_path = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    try:

        # Save uploaded file
        file.save(file_path)

        # Extract text
        extracted_text = extract_text(
            file_path,
            extension
        )

        # Check whether text was extracted
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

        # Save information in session
        session["uploaded_file"] = file.filename
        session["uploaded_path"] = file_path
        session["document_text"] = extracted_text

        # Start a fresh conversation for the uploaded notes
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


    # Study mode instructions

    if study_mode == "explain":

        instruction = """
Explain the topic clearly for a student.

Reply in the same language as the student's question.

Use:
- Simple language
- Clear headings
- Bullet points
- Examples when useful

If uploaded study material is available, base the explanation
mainly on that material.
"""


    elif study_mode == "summarize":

        instruction = """
Summarize the topic clearly.

Reply in the same language as the student's question.

Include the important points.

Use:
- Clear headings
- Bullet points
- Short explanations

If uploaded study material is available, summarize that material.
"""


    elif study_mode == "quiz":

        instruction = """
Create a short quiz about the given topic.

Reply in the same language as the student's question.

Give 5 questions.

Use a mixture of:
- Multiple-choice questions
- Short-answer questions

Provide an answer key separately.

If uploaded study material is available, create the quiz mainly
from that material.
"""


    elif study_mode == "doubt":

        instruction = """
Answer the student's doubt clearly.

Reply in the same language as the student's question.

Explain the concept step by step.

Use a simple example when useful.

If uploaded study material is available, use it as the main source.
"""


    else:

        instruction = """
Help the student understand the topic clearly.

Reply in the same language as the student's question.
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


    # Get uploaded study material
    document_text = session.get(
        "document_text",
        ""
    )


    # Limit document text sent to the AI
    # This prevents extremely large requests.
    maximum_document_chars = 50000

    if document_text:

        document_for_ai = document_text[
            :maximum_document_chars
        ]

        notes_instruction = f"""
The student has uploaded study material.

Use the following study material as the main source
when answering questions related to it.

----- BEGIN STUDY MATERIAL -----

{document_for_ai}

----- END STUDY MATERIAL -----

If the answer is not available in the study material,
clearly say that it is not found in the uploaded material.
"""


    else:

        notes_instruction = """
No study material has been uploaded.
Answer the student's question normally.
"""


    # Add current instructions
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


    # Add user's question
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

    # Remove uploaded file
    uploaded_path = session.get(
        "uploaded_path"
    )

    if uploaded_path:

        try:

            if os.path.exists(uploaded_path):
                os.remove(uploaded_path)

        except Exception as error:

            print("File Delete Error:", error)


    # Clear session
    session.clear()

    # Create new conversation
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

    app.run(
        debug=True
    )
