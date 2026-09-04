from flask import Flask, render_template, request, session
from groq import Groq
import os

app = Flask(__name__)

# Secret key for Flask sessions
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")

# Get Groq API key from environment variable
api_key = os.environ.get("GROQ_API_KEY")

# Connect to Groq
client = Groq(api_key=api_key)


system_instruction = """
You are an AI Study Assistant.

Help students understand their subjects.

Rules:
1. Explain concepts clearly and simply.
2. Break difficult topics into smaller parts.
3. Use examples when useful.
4. Use headings and bullet points.
5. Be educational and easy to understand.
6. Remember the previous messages in the current conversation.
7. Understand follow-up questions using the previous conversation as context.
"""


@app.route("/")
def home():

    # Create conversation history if it does not exist
    if "conversation" not in session:
        session["conversation"] = [
            {
                "role": "system",
                "content": system_instruction
            }
        ]

    return render_template(
        "index.html",
        answer=None
    )


@app.route("/ask", methods=["POST"])
def ask():

    user_question = request.form.get("question")
    study_mode = request.form.get("mode")

    if study_mode == "explain":
        instruction = """
        Explain the topic clearly for a student.
        Use simple language, headings, bullet points and examples.
        """

    elif study_mode == "summarize":
        instruction = """
        Summarize the topic clearly.
        Include only the important points.
        Use headings and bullet points.
        """

    elif study_mode == "quiz":
        instruction = """
        Create a short quiz about the given topic.
        Give 5 questions.
        Include an answer key at the end.
        """

    elif study_mode == "doubt":
        instruction = """
        Answer the student's doubt clearly.
        Explain the concept step by step.
        """

    else:
        instruction = """
        Help the student understand the topic clearly.
        """

    # Get existing conversation
    conversation = session.get("conversation", [])

    # Add the current mode instruction
    conversation.append({
        "role": "system",
        "content": instruction
    })

    # Add user's question
    conversation.append({
        "role": "user",
        "content": user_question
    })

    # Send complete conversation to Groq
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=conversation
    )

    # Get AI answer
    answer = response.choices[0].message.content

    # Save AI answer in conversation
    conversation.append({
        "role": "assistant",
        "content": answer
    })

    # Save updated conversation
    session["conversation"] = conversation
    session.modified = True

    return render_template(
        "index.html",
        question=user_question,
        answer=answer,
        selected_mode=study_mode
    )


@app.route("/clear")
def clear():

    # Clear conversation memory
    session.pop("conversation", None)

    return render_template(
        "index.html",
        answer=None
    )


if __name__ == "__main__":
    app.run(debug=True)
