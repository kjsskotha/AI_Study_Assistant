from flask import Flask, render_template, request, redirect, url_for, session
from groq import Groq
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document
import os
import uuid
import json

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "docx"}

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

MODEL_NAME = "openai/gpt-oss-20b"

DATA_FOLDER = "user_data"
os.makedirs(DATA_FOLDER, exist_ok=True)


# ==================================================
# SESSION / STORAGE
# ==================================================

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


def get_quiz_file():
    return os.path.join(
        get_user_folder(),
        "quiz.json"
    )


def get_flashcards_file():
    return os.path.join(
        get_user_folder(),
        "flashcards.json"
    )


def get_progress_file():
    return os.path.join(
        get_user_folder(),
        "progress.json"
    )


# ==================================================
# PROGRESS
# ==================================================

def default_progress():

    return {
        "questions_asked": 0,
        "notes_uploaded": 0,
        "quiz_attempts": 0,
        "quiz_questions": 0,
        "quiz_correct": 0,
        "flashcard_sets": 0
    }


def load_progress():

    path = get_progress_file()

    if not os.path.exists(path):
        return default_progress()

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            progress = json.load(file)

        default = default_progress()

        for key in default:
            if key not in progress:
                progress[key] = default[key]

        return progress

    except:

        return default_progress()


def save_progress(progress):

    with open(
        get_progress_file(),
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            progress,
            file,
            ensure_ascii=False,
            indent=2
        )


def update_progress(key, amount=1):

    progress = load_progress()

    if key not in progress:
        progress[key] = 0

    progress[key] += amount

    save_progress(progress)


# ==================================================
# CONVERSATION
# ==================================================

def save_conversation(conversation):

    with open(
        get_conversation_file(),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            json.dumps(
                conversation,
                ensure_ascii=False
            )
        )


def load_conversation():

    path = get_conversation_file()

    if not os.path.exists(path):
        return []

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.loads(file.read())

    except:

        return []


# ==================================================
# NOTES
# ==================================================

def save_notes(notes):

    with open(
        get_notes_file(),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(notes)


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


# ==================================================
# FILENAME
# ==================================================

def save_filename(filename):

    with open(
        get_filename_file(),
        "w",
        encoding="utf-8"
    ) as file:

        file.write(filename)


def load_filename():

    path = get_filename_file()

    if not os.path.exists(path):
        return ""

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


# ==================================================
# QUIZ
# ==================================================

def save_quiz(quiz):

    with open(
        get_quiz_file(),
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            quiz,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_quiz():

    path = get_quiz_file()

    if not os.path.exists(path):
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except:

        return None


# ==================================================
# FLASHCARDS
# ==================================================

def save_flashcards(flashcards):

    with open(
        get_flashcards_file(),
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            flashcards,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_flashcards():

    path = get_flashcards_file()

    if not os.path.exists(path):
        return None

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except:

        return None


# ==================================================
# FILE EXTRACTION
# ==================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


def extract_pdf_text(file_path):

    text = ""

    reader = PdfReader(file_path)

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


def extract_docx_text(file_path):

    document = Document(file_path)

    text = ""

    for paragraph in document.paragraphs:

        text += paragraph.text + "\n"

    return text


def extract_text(file_path, filename):

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    if extension == "pdf":
        return extract_pdf_text(file_path)

    if extension == "docx":
        return extract_docx_text(file_path)

    return ""


# ==================================================
# HOME
# ==================================================

@app.route("/")
def home():

    conversation = load_conversation()
    notes = load_notes()
    filename = load_filename()

    quiz = load_quiz()
    flashcards = load_flashcards()

    progress = load_progress()

    return render_template(
        "index.html",
        conversation=conversation,
        notes=notes,
        filename=filename,
        quiz=quiz,
        flashcards=flashcards,
        progress=progress
    )


# ==================================================
# UPLOAD
# ==================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    if "file" not in request.files:

        return redirect(
            url_for("home")
        )

    file = request.files["file"]

    if file.filename == "":

        return redirect(
            url_for("home")
        )

    if not allowed_file(file.filename):

        return redirect(
            url_for("home")
        )

    filename = secure_filename(
        file.filename
    )

    user_folder = get_user_folder()

    file_path = os.path.join(
        user_folder,
        filename
    )

    file.save(file_path)

    try:

        extracted_text = extract_text(
            file_path,
            filename
        )

        if not extracted_text.strip():

            os.remove(file_path)

            return redirect(
                url_for("home")
            )

        save_notes(extracted_text)

        save_filename(filename)

        # New notes remove old generated material

        quiz_path = get_quiz_file()

        if os.path.exists(quiz_path):
            os.remove(quiz_path)

        flashcards_path = get_flashcards_file()

        if os.path.exists(flashcards_path):
            os.remove(flashcards_path)

        # Start new conversation

        save_conversation([])

        # Progress

        update_progress(
            "notes_uploaded"
        )

    except Exception as error:

        print(
            "Upload error:",
            error
        )

        if os.path.exists(file_path):
            os.remove(file_path)

    return redirect(
        url_for("home")
    )


# ==================================================
# ASK AI
# ==================================================

@app.route(
    "/ask",
    methods=["POST"]
)
def ask():

    question = request.form.get(
        "question",
        ""
    ).strip()

    study_mode = request.form.get(
        "mode",
        "explain"
    )

    if not question:

        return redirect(
            url_for("home")
        )

    if study_mode == "quiz":

        return redirect(
            url_for("home")
        )

    if study_mode == "flashcards":

        return redirect(
            url_for("home")
        )

    notes = load_notes()

    conversation = load_conversation()


    if study_mode == "explain":

        instruction = """
You are an AI Study Assistant.

Explain the student's question clearly and accurately.

Reply in the same language as the student's question.

Use simple, student-friendly language.

Break difficult concepts into smaller parts.

Use examples when helpful.

If the uploaded notes are available,
use them as supporting study material.
"""


    elif study_mode == "summarize":

        instruction = """
You are an AI Study Assistant.

Summarize the student's topic clearly.

Reply in the same language as the student's question.

Focus on important points.

Use headings and bullet points where useful.

If uploaded notes are available,
use them as the main source.
"""


    elif study_mode == "quizme":

        instruction = """
You are an AI Study Assistant.

Create a short practice quiz for the student.

Reply in the same language as the student's question.

Ask clear questions based mainly on
the uploaded notes if available.

Do not immediately give all the answers.

Wait for the student to answer and then
evaluate their answers.
"""


    elif study_mode == "doubt":

        instruction = """
You are an AI Study Assistant.

Help the student understand their doubt.

Reply in the same language as the student's question.

Explain the concept step by step.

Correct misunderstandings politely.

Keep the explanation student-friendly.
"""


    elif study_mode == "notes":

        instruction = """
You are an AI Study Assistant.

Use the student's uploaded study material
as the MAIN source.

Reply in the same language as the student's question.

Do not invent information that is not supported
by the uploaded notes.

Organize important exam questions into:

1. Very Short Answer Questions
2. Short Answer Questions
3. Long Answer Questions

Include answers only when the student asks for answers.

If the student asks to generate important
exam questions, create useful questions
from the uploaded notes.
"""


    elif study_mode == "studyplan":

        instruction = """
Create a practical and realistic study plan
for the student.

Reply in the same language as the student's question.

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

Do not suggest studying continuously without breaks.

Include reasonable short breaks.

If the student has not provided enough information,
make a sensible general study plan and clearly
state the assumptions you made.
"""


    else:

        instruction = """
You are an AI Study Assistant.

Help the student with their question.

Reply in the same language as the student's question.

Keep the answer clear and student-friendly.
"""


    # Notes context

    notes_context = ""

    if notes:

        notes_context = f"""

UPLOADED STUDY MATERIAL:

{notes[:50000]}

END OF STUDY MATERIAL.
"""


    messages = [
        {
            "role": "system",
            "content": instruction
        }
    ]


    if notes_context:

        messages.append(
            {
                "role": "system",
                "content": notes_context
            }
        )


    for item in conversation[-20:]:

        messages.append(
            {
                "role": item["role"],
                "content": item["content"]
            }
        )


    messages.append(
        {
            "role": "user",
            "content": question
        }
    )


    try:

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=messages
        )

        answer = response.choices[0].message.content

    except Exception as error:

        print(
            "Groq error:",
            error
        )

        answer = (
            "Sorry, I could not connect to the AI "
            "right now. Please try again."
        )


    conversation.append(
        {
            "role": "user",
            "content": question
        }
    )


    conversation.append(
        {
            "role": "assistant",
            "content": answer
        }
    )


    save_conversation(
        conversation
    )


    # Progress

    update_progress(
        "questions_asked"
    )


    return redirect(
        url_for("home")
    )


# ==================================================
# GENERATE QUIZ
# ==================================================

@app.route(
    "/generate_quiz",
    methods=["POST"]
)
def generate_quiz():

    topic = request.form.get(
        "quiz_topic",
        ""
    ).strip()

    notes = load_notes()

    if not topic:

        topic = (
            "the uploaded study material"
        )


    notes_context = ""

    if notes:

        notes_context = f"""

Use the following uploaded study material
as the main source:

{notes[:50000]}

END OF STUDY MATERIAL.
"""


    prompt = f"""
Create an interactive study quiz.

Topic:
{topic}

{notes_context}

Create EXACTLY 5 multiple-choice questions.

Each question must have exactly 4 options.

Return ONLY valid JSON.

Use this exact structure:

{{
  "title": "Quiz Title",
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "answer": 0,
      "explanation": "Short explanation"
    }}
  ]
}}

Rules:

- answer must be 0, 1, 2, or 3.
- 0 means first option.
- 1 means second option.
- 2 means third option.
- 3 means fourth option.
- Exactly 5 questions.
- Exactly 4 options per question.
- Keep questions educational.
- If notes are provided, mainly use the notes.
- Do not add Markdown.
- Do not add ```json.
"""


    try:

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create valid JSON "
                        "educational quizzes."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )


        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )


        if result.startswith("```"):

            result = (
                result
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )


        quiz = json.loads(result)


        if "questions" not in quiz:

            raise ValueError(
                "Invalid quiz format"
            )


        if len(quiz["questions"]) != 5:

            raise ValueError(
                "Quiz must contain 5 questions"
            )


        for question in quiz["questions"]:

            if len(question["options"]) != 4:

                raise ValueError(
                    "Each question needs 4 options"
                )

            if question["answer"] not in [
                0, 1, 2, 3
            ]:

                raise ValueError(
                    "Invalid answer index"
                )


        save_quiz(quiz)


        # Remove old flashcards

        flashcards_path = get_flashcards_file()

        if os.path.exists(
            flashcards_path
        ):

            os.remove(
                flashcards_path
            )


    except Exception as error:

        print(
            "Quiz generation error:",
            error
        )


    return redirect(
        url_for("home")
    )


# ==================================================
# GENERATE FLASHCARDS
# ==================================================

@app.route(
    "/generate_flashcards",
    methods=["POST"]
)
def generate_flashcards():

    topic = request.form.get(
        "flashcard_topic",
        ""
    ).strip()

    notes = load_notes()

    if not topic:

        topic = (
            "the uploaded study material"
        )


    notes_context = ""

    if notes:

        notes_context = f"""

Use the following uploaded study material
as the MAIN source:

{notes[:50000]}

END OF STUDY MATERIAL.
"""


    prompt = f"""
Create interactive study flashcards.

Topic:
{topic}

{notes_context}

Create EXACTLY 10 flashcards.

Each flashcard must contain:

- question
- answer

Return ONLY valid JSON.

Use this exact structure:

{{
  "title": "Flashcards",
  "cards": [
    {{
      "question": "Question text",
      "answer": "Answer text"
    }}
  ]
}}

Rules:

- Exactly 10 flashcards.
- Each card must have a clear question.
- Each card must have a correct and useful answer.
- Focus on important definitions, concepts,
  facts, formulas, differences, and revision points.
- If uploaded notes are available,
  mainly use the notes.
- Do not invent information that is not
  supported by the notes.
- Keep answers clear and student-friendly.
- Reply in the same language as the topic/question
  when possible.
- Do not add Markdown.
- Do not add ```json.
"""


    try:

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You create valid JSON "
                        "educational flashcards."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )


        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )


        if result.startswith("```"):

            result = (
                result
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )


        flashcards = json.loads(result)


        if "cards" not in flashcards:

            raise ValueError(
                "Invalid flashcard format"
            )


        if len(flashcards["cards"]) != 10:

            raise ValueError(
                "Flashcards must contain 10 cards"
            )


        for card in flashcards["cards"]:

            if not card.get("question"):

                raise ValueError(
                    "Flashcard question missing"
                )

            if not card.get("answer"):

                raise ValueError(
                    "Flashcard answer missing"
                )


        save_flashcards(
            flashcards
        )


        # Remove old quiz

        quiz_path = get_quiz_file()

        if os.path.exists(quiz_path):

            os.remove(quiz_path)


        # Progress

        update_progress(
            "flashcard_sets"
        )


    except Exception as error:

        print(
            "Flashcard generation error:",
            error
        )


    return redirect(
        url_for("home")
    )


# ==================================================
# SUBMIT QUIZ
# ==================================================

@app.route(
    "/submit_quiz",
    methods=["POST"]
)
def submit_quiz():

    quiz = load_quiz()

    if not quiz:

        return redirect(
            url_for("home")
        )


    score = 0

    results = []


    for index, question in enumerate(
        quiz["questions"]
    ):

        selected = request.form.get(
            f"question_{index}"
        )

        correct_answer = question["answer"]


        is_correct = (
            selected is not None
            and int(selected)
            == correct_answer
        )


        if is_correct:

            score += 1


        results.append(
            {
                "question":
                    question["question"],

                "selected":
                    selected,

                "correct":
                    correct_answer,

                "options":
                    question["options"],

                "explanation":
                    question.get(
                        "explanation",
                        ""
                    ),

                "is_correct":
                    is_correct
            }
        )


    quiz["result"] = {

        "score":
            score,

        "total":
            len(
                quiz["questions"]
            ),

        "results":
            results
    }


    save_quiz(quiz)


    # Progress

    update_progress(
        "quiz_attempts"
    )

    update_progress(
        "quiz_questions",
        len(quiz["questions"])
    )

    update_progress(
        "quiz_correct",
        score
    )


    return redirect(
        url_for("home")
    )


# ==================================================
# CLEAR
# ==================================================

@app.route(
    "/clear",
    methods=["POST"]
)
def clear():

    folder = get_user_folder()

    if os.path.exists(folder):

        for filename in os.listdir(folder):

            path = os.path.join(
                folder,
                filename
            )

            if os.path.isfile(path):

                os.remove(path)


    return redirect(
        url_for("home")
    )


# ==================================================
# FILE TOO LARGE
# ==================================================

@app.errorhandler(413)
def file_too_large(error):

    return (
        "File is too large. Maximum size is 10 MB.",
        413
    )


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
