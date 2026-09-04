from flask import Flask, render_template, request, session
from groq import Groq
import os
import uuid
import PyPDF2
from docx import Document


app = Flask(__name__)


# --------------------------------------------------
# FLASK SECRET KEY
# --------------------------------------------------

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)


# --------------------------------------------------
# FILE UPLOAD SETTINGS
# --------------------------------------------------

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# --------------------------------------------------
# GROQ API
# --------------------------------------------------

api_key = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=api_key)


# --------------------------------------------------
# SERVER STORAGE
# --------------------------------------------------

DATA_FOLDER = "user_data"

os.makedirs(
    DATA_FOLDER,
    exist_ok=True
)


# --------------------------------------------------
# MAIN AI INSTRUCTIONS
# --------------------------------------------------

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
# GET OR CREATE SESSION ID
# --------------------------------------------------

def get_session_id():

    if "session_id" not in session:

        session["session_id"] = str(
            uuid.uuid4()
        )

        session.modified = True

    return session["session_id"]


# --------------------------------------------------
# GET USER FOLDER
# --------------------------------------------------

def get_user_folder():

    session_id = get_session_id()

    folder = os.path.join(
        DATA_FOLDER,
        session_id
    )

    os.makedirs(
        folder,
        exist_ok=True
    )

    return folder


# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

def get_conversation_file():

    return os.path.join(
        get_user_folder(),
        "conversation.txt"
    )


def get_notes_file():

    return os.path.join(
        get_user_folder(),
        "notes.txt"
    )


def get_filename_file():

    return os.path.join(
        get_user_folder(),
        "filename.txt"
    )


# --------------------------------------------------
# GET UPLOADED FILE NAME
# --------------------------------------------------

def get_uploaded_file_name():

    path = get_filename_file()

    if os.path.exists(path):

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    return None


# --------------------------------------------------
# SAVE UPLOADED FILE NAME
# --------------------------------------------------

def save_uploaded_file_name(filename):

    path = get_filename_file()

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(filename)


# --------------------------------------------------
# SAVE CONVERSATION
# --------------------------------------------------

def save_conversation(conversation):

    path = get_conversation_file()

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        for message in conversation:

            file.write(
                message["role"] + "\n"
            )

            file.write(
                message["content"] + "\n"
            )

            file.write(
                "-----MESSAGE-END-----\n"
            )


# --------------------------------------------------
# LOAD CONVERSATION
# --------------------------------------------------

def load_conversation():

    path = get_conversation_file()

    if not os.path.exists(path):

        return [
            {
                "role": "system",
                "content": system_instruction
            }
        ]


    conversation = []


    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        data = file.read()


    blocks = data.split(
        "-----MESSAGE-END-----"
    )


    for block in blocks:

        block = block.strip()

        if not block:

            continue


        lines = block.split(
            "\n",
            1
        )


        if len(lines) != 2:

            continue


        role = lines[0].strip()

        content = lines[1].strip()


        if role in [
            "system",
            "user",
            "assistant"
        ]:

            conversation.append(
                {
                    "role": role,
                    "content": content
                }
            )


    if not conversation:

        conversation = [
            {
                "role": "system",
                "content": system_instruction
            }
        ]


    return conversation


# --------------------------------------------------
# SAVE NOTES
# --------------------------------------------------

def save_notes(text):

    path = get_notes_file()

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(text)


# --------------------------------------------------
# LOAD NOTES
# --------------------------------------------------

def load_notes():

    path = get_notes_file()

    if not os.path.exists(path):

        return ""


    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


# --------------------------------------------------
# PDF TEXT EXTRACTION
# --------------------------------------------------

def extract_pdf_text(file_path):

    text = ""


    with open(
        file_path,
        "rb"
    ) as file:

        reader = PyPDF2.PdfReader(
            file
        )


        for page in reader.pages:

            page_text = page.extract_text()


            if page_text:

                text += (
                    page_text
                    + "\n"
                )


    return text


# --------------------------------------------------
# DOCX TEXT EXTRACTION
# --------------------------------------------------

def extract_docx_text(file_path):

    document = Document(
        file_path
    )

    text = ""


    for paragraph in document.paragraphs:

        if paragraph.text.strip():

            text += (
                paragraph.text
                + "\n"
            )


    return text


# --------------------------------------------------
# SELECT TEXT EXTRACTION METHOD
# --------------------------------------------------

def extract_text(
    file_path,
    extension
):

    if extension == ".pdf":

        return extract_pdf_text(
            file_path
        )


    elif extension == ".docx":

        return extract_docx_text(
            file_path
        )


    return ""


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():

    uploaded_file = (
        get_uploaded_file_name()
    )


    return render_template(
        "index.html",
        answer=None,
        uploaded_file=uploaded_file
    )


# --------------------------------------------------
# UPLOAD STUDY MATERIAL
# --------------------------------------------------

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    file = request.files.get(
        "study_file"
    )


    if not file or file.filename == "":

        return render_template(
            "index.html",
            answer="Please select a PDF or DOCX file.",
            uploaded_file=get_uploaded_file_name()
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
            uploaded_file=get_uploaded_file_name()
        )


    # Create unique file name

    unique_name = (
        str(uuid.uuid4())
        + extension
    )


    file_path = os.path.join(
        get_user_folder(),
        unique_name
    )


    try:

        # Save file

        file.save(
            file_path
        )


        # Extract text

        extracted_text = extract_text(
            file_path,
            extension
        )


        # Check extracted text

        if not extracted_text.strip():

            os.remove(
                file_path
            )


            return render_template(
                "index.html",
                answer=(
                    "I could not extract readable text from this file. "
                    "Please try a text-based PDF or DOCX file."
                ),
                uploaded_file=None
            )


        # Save notes

        save_notes(
            extracted_text
        )


        # Save original file name

        save_uploaded_file_name(
            file.filename
        )


        # Start fresh conversation

        conversation = [

            {
                "role": "system",
                "content": system_instruction
            }

        ]


        save_conversation(
            conversation
        )


        return render_template(

            "index.html",

            answer=(
                "Your study material was uploaded successfully. "
                "You can now ask questions about it."
            ),

            uploaded_file=file.filename

        )


    except Exception as error:

        print(
            "File Error:",
            error
        )


        if os.path.exists(
            file_path
        ):

            os.remove(
                file_path
            )


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

@app.route(
    "/ask",
    methods=["POST"]
)
def ask():

    user_question = request.form.get(
        "question",
        ""
    ).strip()


    study_mode = request.form.get(
        "mode",
        "explain"
    )


    uploaded_file = (
        get_uploaded_file_name()
    )


    # Check question

    if not user_question:

        return render_template(

            "index.html",

            answer=(
                "Please enter a question or topic."
            ),

            question="",

            selected_mode=study_mode,

            uploaded_file=uploaded_file

        )


    # --------------------------------------------------
    # EXPLAIN MODE
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

If study material is uploaded,
use it as the main source.
"""


    # --------------------------------------------------
    # SUMMARIZE MODE
    # --------------------------------------------------

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

If study material is uploaded,
summarize mainly from that material.
"""


    # --------------------------------------------------
    # QUIZ MODE
    # --------------------------------------------------

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


    # --------------------------------------------------
    # DOUBT MODE
    # --------------------------------------------------

    elif study_mode == "doubt":

        instruction = """
Answer the student's doubt clearly.

Reply in the same language as the student's question.

Explain the concept step by step.

Use a simple example when useful.

If study material is uploaded,
use it as the main source.
"""


    # --------------------------------------------------
    # NOTES MODE
    # --------------------------------------------------

    elif study_mode == "notes":

        instruction = """
The student wants to study from their uploaded notes.

Reply in the same language as the student's question.

Use the uploaded study material as the MAIN SOURCE.

If the student asks for:

- Important exam questions
- Important topics
- Important definitions
- Revision questions
- Exam preparation
- Questions from my notes

Create the response mainly from the uploaded material.

For exam questions, organize them into:

1. Very Short Answer Questions
2. Short Answer Questions
3. Long Answer Questions

Do not invent topics that are not present
in the uploaded study material.

If something is not available in the notes,
clearly say that it is not found in the
uploaded material.
"""


    # --------------------------------------------------
    # FLASHCARDS MODE
    # --------------------------------------------------

    elif study_mode == "flashcards":

        instruction = """
The student wants to create AI flashcards
from their uploaded study material.

Reply in the same language as the student's question.

Create useful study flashcards mainly from
the uploaded study material.

Each flashcard must contain:

FLASHCARD 1

Question:
A clear question about an important concept.

Answer:
A short and accurate answer.

Create around 10 flashcards.

Focus on:
- Important definitions
- Important concepts
- Key facts
- Important formulas when present
- Important differences
- Important points for revision

Keep the answers short and easy to remember.

Do not invent information that is not present
in the uploaded study material.

If the requested information is not available
in the notes, clearly say so.
"""


    else:

        instruction = """
Help the student understand the topic clearly.

Reply in the same language as the student's question.
"""


    # --------------------------------------------------
    # LOAD CONVERSATION
    # --------------------------------------------------

    conversation = load_conversation()


    # --------------------------------------------------
    # LOAD NOTES
    # --------------------------------------------------

    document_text = load_notes()


    # --------------------------------------------------
    # NOTES FOR AI
    # --------------------------------------------------

    maximum_document_chars = 50000


    if document_text:

        document_for_ai = document_text[
            :maximum_document_chars
        ]


        notes_instruction = f"""
The student has uploaded study material.

Use this material as the main source.

Do not claim that information is in the
material if it is not actually present.

----- BEGIN STUDY MATERIAL -----

{document_for_ai}

----- END STUDY MATERIAL -----
"""


    else:

        notes_instruction = """
No study material has been uploaded.

Answer the student's question normally.

If the student selected a notes-based mode,
tell them that they need to upload study
material first.
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


    # --------------------------------------------------
    # ADD USER QUESTION
    # --------------------------------------------------

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


        answer = (
            response
            .choices[0]
            .message
            .content
        )


    except Exception as error:

        print(
            "Groq Error:",
            error
        )


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


    save_conversation(
        conversation
    )


    # --------------------------------------------------
    # DISPLAY ANSWER
    # --------------------------------------------------

    return render_template(

        "index.html",

        question=user_question,

        answer=answer,

        selected_mode=study_mode,

        uploaded_file=uploaded_file

    )


# --------------------------------------------------
# CLEAR CONVERSATION
# --------------------------------------------------

@app.route("/clear")
def clear():

    user_folder = get_user_folder()


    try:

        for filename in os.listdir(
            user_folder
        ):

            file_path = os.path.join(
                user_folder,
                filename
            )


            if os.path.isfile(
                file_path
            ):

                os.remove(
                    file_path
                )


    except Exception as error:

        print(
            "Clear Error:",
            error
        )


    # Create fresh conversation

    conversation = [

        {
            "role": "system",
            "content": system_instruction
        }

    ]


    save_conversation(
        conversation
    )


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

        uploaded_file=get_uploaded_file_name()

    ), 413


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True
    )
