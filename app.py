from flask import Flask, render_template, request, session, redirect, url_for
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

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

DATA_FOLDER = "user_data"
os.makedirs(DATA_FOLDER, exist_ok=True)


# =========================================
# SESSION / USER STORAGE
# =========================================

def get_session_id():

    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    return session["session_id"]


def get_user_folder():

    folder = os.path.join(
        DATA_FOLDER,
        get_session_id()
    )

    os.makedirs(folder, exist_ok=True)

    return folder


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


# =========================================
# FILE NAME
# =========================================

def save_uploaded_file_name(filename):

    with open(
        get_filename_file(),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(filename)


def get_uploaded_file_name():

    filename_file = get_filename_file()

    if os.path.exists(filename_file):

        with open(
            filename_file,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    return ""


# =========================================
# CONVERSATION
# =========================================

def save_conversation(conversation):

    with open(
        get_conversation_file(),
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


def load_conversation():

    filename = get_conversation_file()

    if not os.path.exists(filename):
        return []

    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:

        text = file.read()

    if not text.strip():
        return []

    blocks = text.split(
        "-----MESSAGE-END-----"
    )

    conversation = []

    for block in blocks:

        block = block.strip()

        if not block:
            continue

        lines = block.split("\n", 1)

        if len(lines) != 2:
            continue

        conversation.append({
            "role": lines[0].strip(),
            "content": lines[1].strip()
        })

    return conversation


# =========================================
# NOTES
# =========================================

def save_notes(text):

    with open(
        get_notes_file(),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(text)


def load_notes():

    filename = get_notes_file()

    if not os.path.exists(filename):
        return ""

    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


# =========================================
# PDF
# =========================================

def extract_pdf_text(file):

    text = ""

    reader = PyPDF2.PdfReader(file)

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:

            text += page_text
            text += "\n"

    return text


# =========================================
# DOCX
# =========================================

def extract_docx_text(file):

    document = Document(file)

    text = ""

    for paragraph in document.paragraphs:

        if paragraph.text.strip():

            text += paragraph.text
            text += "\n"

    return text


# =========================================
# TEXT EXTRACTION
# =========================================

def extract_text(file, filename):

    extension = filename.lower().split(".")[-1]

    if extension == "pdf":

        return extract_pdf_text(file)

    if extension == "docx":

        return extract_docx_text(file)

    return ""


# =========================================
# HOME
# =========================================

@app.route("/")
def home():

    return render_template(
        "index.html",
        conversation=load_conversation(),
        notes=load_notes(),
        filename=get_uploaded_file_name()
    )


# =========================================
# UPLOAD
# =========================================

@app.route("/upload", methods=["POST"])
def upload():

    uploaded_file = request.files.get("file")

    if not uploaded_file:
        return redirect(url_for("home"))

    filename = uploaded_file.filename

    if not filename:
        return redirect(url_for("home"))

    extension = filename.lower().split(".")[-1]

    if extension not in ["pdf", "docx"]:
        return redirect(url_for("home"))

    try:

        text = extract_text(
            uploaded_file,
            filename
        )

        if not text.strip():
            return redirect(url_for("home"))

        save_notes(text)

        safe_filename = os.path.basename(
            filename
        )

        file_path = os.path.join(
            get_user_folder(),
            safe_filename
        )

        uploaded_file.seek(0)

        uploaded_file.save(file_path)

        save_uploaded_file_name(
            safe_filename
        )

        save_conversation([])

        return redirect(url_for("home"))

    except Exception as e:

        print("Upload error:", e)

        return redirect(url_for("home"))


# =========================================
# ASK AI
# =========================================

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

        return redirect(url_for("home"))

    notes = load_notes()

    conversation = load_conversation()


    # =====================================
    # BASE INSTRUCTION
    # =====================================

    base_instruction = """

You are an AI Study Assistant.

Help students understand academic subjects
clearly and accurately.

Understand questions written in any language.

Reply in the same language as the student's
question by default.

If the student explicitly asks for another
language, use that language.

Keep technical terms accurate.

Use simple, student-friendly explanations.

Use headings, bullet points, numbered lists,
tables, formulas and examples when useful.

"""


    # =====================================
    # EXPLAIN
    # =====================================

    if study_mode == "explain":

        instruction = """

Explain the topic clearly for a student.

Start with a simple definition.

Explain the concept step by step.

Give a simple example when useful.

End with important points to remember.

"""


    # =====================================
    # SUMMARIZE
    # =====================================

    elif study_mode == "summarize":

        instruction = """

Summarize the topic clearly.

Include:

- Key points
- Important definitions
- Important formulas
- Important examples
- Exam points

Keep the summary concise and useful for
revision.

"""


    # =====================================
    # IMPROVED QUIZ
    # =====================================

    elif study_mode == "quiz":

        instruction = """

Create a practice quiz for the student.

Create exactly 5 multiple-choice questions.

Use this format for every question:

### Question 1

Question text

A) Option

B) Option

C) Option

D) Option


Do NOT show the correct answers immediately.

After all 5 questions, write:

### Answer Format

Ask the student to reply like:

1-A
2-C
3-B
4-D
5-A

Tell the student that after they submit
their answers, you will check them and provide:

- Score
- Correct answers
- Explanation for each question
- Topics that need more revision

If uploaded study notes are available,
create the quiz mainly from those notes.

Do not invent information that is not
supported by the uploaded notes.

Keep the questions suitable for a student.

"""


    # =====================================
    # DOUBT
    # =====================================

    elif study_mode == "doubt":

        instruction = """

The student has a doubt.

Understand what the student is confused
about.

Explain the concept step by step.

Give a simple example if useful.

Correct misunderstandings politely.

"""


    # =====================================
    # NOTES
    # =====================================

    elif study_mode == "notes":

        instruction = """

Use the uploaded study material as the
main source.

Do not invent information that is not
supported by the uploaded notes.

Generate important exam questions.

Organize them into:

1. Very Short Answer Questions
2. Short Answer Questions
3. Long Answer Questions

Focus on important definitions,
concepts, differences, explanations,
examples and formulas present in the notes.

"""


    # =====================================
    # FLASHCARDS
    # =====================================

    elif study_mode == "flashcards":

        instruction = """

Create around 10 useful study flashcards.

Each flashcard should contain:

Question:
Answer:

Focus on:

- Definitions
- Important concepts
- Facts
- Formulas
- Differences
- Revision points

If notes are uploaded, use them as the
main source.

Do not invent information that is not
supported by the notes.

Keep flashcards short and useful.

"""


    # =====================================
    # STUDY PLAN
    # =====================================

    elif study_mode == "studyplan":

        instruction = """

Create a practical and realistic study plan.

Understand:

- Subject
- Number of days
- Available study time
- Exam date if provided
- Uploaded study material

If notes are uploaded, build the plan
mainly around those notes.

Organize the response using:

1. Study Plan Overview
2. Daily Schedule
3. Topics to Study
4. Practice / Questions
5. Revision
6. Final Review

For every day mention:

- What to study
- Approximate time
- What to practice
- What to revise

Include reasonable short breaks.

Keep the plan realistic.

"""


    else:

        instruction = """

Answer the student's question clearly.

"""


    # =====================================
    # NOTES CONTEXT
    # =====================================

    notes_context = ""

    if notes.strip():

        limited_notes = notes[:50000]

        notes_context = f"""

Uploaded study material:

-------------------------
{limited_notes}
-------------------------

Use this material when relevant.

"""


    # =====================================
    # SYSTEM PROMPT
    # =====================================

    system_prompt = (
        base_instruction
        + instruction
        + notes_context
    )


    # =====================================
    # MESSAGES
    # =====================================

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]


    recent_conversation = conversation[-10:]


    for message in recent_conversation:

        messages.append({
            "role": message["role"],
            "content": message["content"]
        })


    messages.append({
        "role": "user",
        "content": user_question
    })


    # =====================================
    # GROQ
    # =====================================

    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-20b",

            messages=messages

        )

        ai_response = (
            response
            .choices[0]
            .message
            .content
        )

    except Exception as e:

        print("Groq error:", e)

        ai_response = """

Sorry, I could not process your request
right now.

Please try again in a moment.

"""


    # =====================================
    # SAVE
    # =====================================

    conversation.append({

        "role": "user",

        "content": user_question

    })

    conversation.append({

        "role": "assistant",

        "content": ai_response

    })

    save_conversation(
        conversation
    )


    return redirect(
        url_for("home")
    )


# =========================================
# CLEAR
# =========================================

@app.route("/clear")
def clear():

    user_folder = get_user_folder()


    for filename in [
        "conversation.txt",
        "notes.txt",
        "filename.txt"
    ]:

        file_path = os.path.join(
            user_folder,
            filename
        )

        if os.path.exists(file_path):

            os.remove(file_path)


    if os.path.exists(user_folder):

        for filename in os.listdir(user_folder):

            file_path = os.path.join(
                user_folder,
                filename
            )

            if os.path.isfile(file_path):

                try:
                    os.remove(file_path)
                except Exception:
                    pass


    return redirect(
        url_for("home")
    )


# =========================================
# FILE TOO LARGE
# =========================================

@app.errorhandler(413)
def too_large(error):

    return """

    <h2>File is too large.</h2>

    <p>
    Please upload a PDF or DOCX file
    smaller than 10 MB.
    </p>

    <a href="/">Go Back</a>

    """, 413


# =========================================
# RUN
# =========================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
