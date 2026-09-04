from flask import Flask, render_template, request, session, redirect, url_for
from groq import Groq
import os
import uuid
import PyPDF2
from docx import Document

app = Flask(__name__)

# Secret key
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

# Maximum upload size = 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Groq API
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

# Folder for temporary user data
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

    session_id = get_session_id()

    folder = os.path.join(
        DATA_FOLDER,
        session_id
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
# FILE NAME STORAGE
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
# CONVERSATION STORAGE
# =========================================

def save_conversation(conversation):

    with open(
        get_conversation_file(),
        "w",
        encoding="utf-8"
    ) as file:

        for message in conversation:

            file.write(
                message["role"]
                + "\n"
            )

            file.write(
                message["content"]
                + "\n"
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

        role = lines[0].strip()
        content = lines[1].strip()

        conversation.append({
            "role": role,
            "content": content
        })

    return conversation


# =========================================
# NOTES STORAGE
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
# PDF TEXT EXTRACTION
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
# DOCX TEXT EXTRACTION
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
# GENERAL TEXT EXTRACTION
# =========================================

def extract_text(file, filename):

    extension = filename.lower().split(".")[-1]

    if extension == "pdf":

        return extract_pdf_text(file)

    elif extension == "docx":

        return extract_docx_text(file)

    return ""


# =========================================
# HOME PAGE
# =========================================

@app.route("/")
def home():

    conversation = load_conversation()

    notes = load_notes()

    filename = get_uploaded_file_name()

    return render_template(
        "index.html",
        conversation=conversation,
        notes=notes,
        filename=filename
    )


# =========================================
# UPLOAD STUDY MATERIAL
# =========================================

@app.route("/upload", methods=["POST"])
def upload():

    uploaded_file = request.files.get(
        "file"
    )

    if not uploaded_file:

        return redirect(
            url_for("home")
        )

    filename = uploaded_file.filename

    if not filename:

        return redirect(
            url_for("home")
        )

    extension = filename.lower().split(".")[-1]

    if extension not in ["pdf", "docx"]:

        return redirect(
            url_for("home")
        )

    try:

        # Extract text
        text = extract_text(
            uploaded_file,
            filename
        )

        if not text.strip():

            return redirect(
                url_for("home")
            )

        # Save notes
        save_notes(text)

        # Save original file
        safe_filename = os.path.basename(
            filename
        )

        file_path = os.path.join(
            get_user_folder(),
            safe_filename
        )

        uploaded_file.seek(0)

        uploaded_file.save(
            file_path
        )

        # Save filename
        save_uploaded_file_name(
            safe_filename
        )

        # Start fresh conversation
        save_conversation([])

        return redirect(
            url_for("home")
        )

    except Exception as e:

        print("Upload error:", e)

        return redirect(
            url_for("home")
        )


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

        return redirect(
            url_for("home")
        )

    notes = load_notes()

    conversation = load_conversation()


    # =====================================
    # MAIN AI INSTRUCTION
    # =====================================

    base_instruction = """
You are an AI Study Assistant.

Your job is to help students understand
academic subjects clearly.

Understand questions written in any language.

Reply in the same language as the student's
question by default.

If the student explicitly asks for another
language, reply in that language.

Support languages such as:

English
Telugu
Hindi
Tamil
Kannada
Malayalam
Bengali
Marathi
Gujarati
Punjabi
Urdu

and other languages.

Keep technical terms accurate.

Use simple, student-friendly explanations.

Use headings, bullet points, numbered lists,
tables, formulas, and examples when useful.

Do not unnecessarily make answers complicated.
"""


    # =====================================
    # EXPLAIN MODE
    # =====================================

    if study_mode == "explain":

        instruction = """
Explain the topic clearly for a student.

Start with a simple definition.

Then explain the concept step by step.

Give a simple example when useful.

End with important points to remember.

Make the explanation easy to understand
for exam preparation.
"""


    # =====================================
    # SUMMARIZE MODE
    # =====================================

    elif study_mode == "summarize":

        instruction = """
Summarize the topic clearly.

Include only the important information.

Use:

- Key points
- Important definitions
- Important formulas if applicable
- Important examples if applicable
- Exam points

Keep the summary concise and useful
for revision.
"""


    # =====================================
    # QUIZ MODE
    # =====================================

    elif study_mode == "quiz":

        instruction = """
Create a short quiz for the student.

Ask around 5 questions.

Mix different types such as:

- Multiple choice
- Short answer
- Concept questions

Do not immediately reveal the answers.

After the student answers,
check the answers and explain mistakes.
"""


    # =====================================
    # DOUBT MODE
    # =====================================

    elif study_mode == "doubt":

        instruction = """
The student has a doubt.

Understand exactly what the student
is confused about.

Explain the concept step by step.

If necessary, give a simple example.

Correct misunderstandings politely.

Keep the explanation student-friendly.
"""


    # =====================================
    # ASK FROM NOTES MODE
    # =====================================

    elif study_mode == "notes":

        instruction = """
Use the uploaded study material as the
main source for your answer.

Do not invent information that is not
supported by the uploaded notes.

Generate important exam questions from
the uploaded study material.

Organize the questions into:

1. Very Short Answer Questions
2. Short Answer Questions
3. Long Answer Questions

Focus on important definitions,
concepts, differences, explanations,
examples, formulas, and other points
that are actually present in the notes.

Reply in the same language as the
student's question.
"""


    # =====================================
    # FLASHCARDS MODE
    # =====================================

    elif study_mode == "flashcards":

        instruction = """
Create around 10 useful study flashcards.

Each flashcard must contain:

Question:
Answer:

Focus on:

- Definitions
- Important concepts
- Facts
- Formulas
- Differences
- Important revision points

If study notes are uploaded,
create the flashcards mainly from
those notes.

Do not invent information that is not
supported by the notes.

Make the flashcards short and useful
for quick revision.

Reply in the same language as the
student's question.
"""


    # =====================================
    # STUDY PLAN MODE
    # =====================================

    elif study_mode == "studyplan":

        instruction = """
Create a practical and realistic study plan
for the student.

Reply in the same language as the student's
question.

Understand the student's:

- Subject or subjects
- Number of days
- Available study time
- Exam or target date if provided
- Uploaded study material if available

If the student has uploaded notes,
build the plan mainly around the topics
in those notes.

Organize the plan clearly.

Use:

1. Study Plan Overview
2. Daily Schedule
3. Topics to Study
4. Practice / Questions
5. Revision
6. Final Review

For each day, mention:

- What to study
- Approximate time
- What to practice
- What to revise

Keep the plan realistic.

Do not suggest studying continuously
without breaks.

Include reasonable short breaks.

If the student has not provided enough
information, make a sensible general
study plan and clearly state the
assumptions you made.
"""


    else:

        instruction = """
Answer the student's question clearly
and helpfully.
"""


    # =====================================
    # NOTES CONTEXT
    # =====================================

    notes_context = ""

    if notes.strip():

        # Limit notes sent to AI
        limited_notes = notes[:50000]

        notes_context = f"""

The student has uploaded study material.

Use it when it is relevant.

Uploaded study material:

-------------------------
{limited_notes}
-------------------------

"""


    # =====================================
    # FINAL SYSTEM PROMPT
    # =====================================

    system_prompt = (
        base_instruction
        + "\n"
        + instruction
        + notes_context
    )


    # =====================================
    # CONVERSATION HISTORY
    # =====================================

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # Keep recent conversation
    recent_conversation = conversation[-10:]

    for message in recent_conversation:

        messages.append({
            "role": message["role"],
            "content": message["content"]
        })


    # Add current question
    messages.append({
        "role": "user",
        "content": user_question
    })


    # =====================================
    # CALL GROQ
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
    # SAVE CONVERSATION
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
# CLEAR CONVERSATION
# =========================================

@app.route("/clear")
def clear():

    user_folder = get_user_folder()

    # Delete conversation
    conversation_file = get_conversation_file()

    if os.path.exists(conversation_file):

        os.remove(conversation_file)


    # Delete notes
    notes_file = get_notes_file()

    if os.path.exists(notes_file):

        os.remove(notes_file)


    # Delete filename
    filename_file = get_filename_file()

    if os.path.exists(filename_file):

        os.remove(filename_file)


    # Delete uploaded files
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
    <p>Please upload a PDF or DOCX file
    smaller than 10 MB.</p>
    <a href="/">Go Back</a>
    """, 413


# =========================================
# RUN APPLICATION
# =========================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
