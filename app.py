from flask import Flask, render_template, request
from groq import Groq
import os

app = Flask(__name__)

# Get API key from environment variable
api_key = os.environ.get("GROQ_API_KEY")

# Connect to Groq
client = Groq(api_key=api_key)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():

    user_question = request.form.get("question")
    study_mode = request.form.get("mode")

    if study_mode == "explain":
        instruction = """
        Explain the topic clearly for a student.
        Use simple language, headings, bullet points and examples.
        Break difficult ideas into smaller parts.
        """

    elif study_mode == "summarize":
        instruction = """
        Summarize the given topic clearly.
        Include only the important points.
        Use headings and bullet points.
        Keep the explanation easy to study and remember.
        """

    elif study_mode == "quiz":
        instruction = """
        Create a short quiz about the given topic.
        Give 5 questions.
        Mix multiple-choice and short-answer questions.
        Do not immediately reveal the answers.
        At the end, provide an answer key separately.
        """

    elif study_mode == "doubt":
        instruction = """
        Answer the student's doubt clearly.
        Explain the concept step by step.
        Use a simple example if useful.
        """

    else:
        instruction = """
        Help the student understand the topic clearly.
        """

    system_instruction = f"""
    You are an AI Study Assistant.

    {instruction}

    Be educational, accurate and easy to understand.
    Do not make the explanation unnecessarily complicated.
    """

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": system_instruction
            },
            {
                "role": "user",
                "content": user_question
            }
        ]
    )

    answer = response.choices[0].message.content

    return render_template(
        "index.html",
        question=user_question,
        answer=answer,
        selected_mode=study_mode
    )


if __name__ == "__main__":
    app.run(debug=True)
