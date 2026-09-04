from flask import Flask, render_template, request
from groq import Groq
import os

app = Flask(__name__)

# Get the API key from an environment variable
api_key = os.environ.get("GROQ_API_KEY")

# Create Groq client
client = Groq(api_key=api_key)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():

    user_question = request.form.get("question")

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": """
                You are an AI Study Assistant.

                Help students understand their subjects.

                Explain concepts clearly and simply.
                Break difficult topics into smaller parts.
                Use examples when useful.
                Use headings and bullet points.
                Be educational and easy to understand.
                """
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
        answer=answer
    )


if __name__ == "__main__":
    app.run(debug=True)