from flask import Flask, render_template, request, session
from groq import Groq
import os

app = Flask(__name__)

# Secret key for Flask sessions
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)

# Get Groq API key from environment variable
api_key = os.environ.get("GROQ_API_KEY")

# Connect to Groq
client = Groq(api_key=api_key)


# Main AI instructions
system_instruction = """
You are an AI Study Assistant for students around the world.

Your job is to help students learn and understand their subjects clearly.

LANGUAGE RULES:
1. Understand questions written in any language.
2. Reply in the same language used by the student by default.
3. If the student explicitly asks for another language, reply in that requested language.
4. Support English, Telugu, Hindi, Tamil, Kannada, Malayalam,
   Bengali, Marathi, Gujarati, Punjabi, Urdu and other languages.
5. Do not unnecessarily translate the student's question.
6. Keep technical terms accurate. If useful, explain difficult
   technical terms in simple words.

STUDY RULES:
1. Explain concepts clearly and simply.
2. Break difficult topics into smaller parts.
3. Use examples when useful.
4. Use headings, bullet points and numbered lists when appropriate.
5. Be educational, accurate and easy to understand.
6. Remember previous messages in the current conversation.
7. Understand follow-up questions using previous conversation context.
8. Adapt the explanation to the student's requested study mode.
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

    # Get user's question and selected study mode
    user_question = request.form.get("question", "").strip()
    study_mode = request.form.get("mode", "explain")

    # Prevent empty questions
    if not user_question:

        return render_template(
            "index.html",
            answer="Please enter a question or topic.",
            question="",
            selected_mode=study_mode
        )


    # Study mode instructions
    if study_mode == "explain":

        instruction = """
Explain the topic clearly for a student.

Reply in the same language as the student's question unless
the student explicitly requests another language.

Use:
- Simple language
- Clear headings
- Bullet points when useful
- Examples when useful

Break difficult concepts into smaller, easy-to-understand parts.
"""


    elif study_mode == "summarize":

        instruction = """
Summarize the given topic clearly.

Reply in the same language as the student's question unless
the student explicitly requests another language.

Include only the important points.

Use:
- Clear headings
- Bullet points
- Short and easy-to-remember explanations
"""


    elif study_mode == "quiz":

        instruction = """
Create a short quiz about the given topic.

Reply in the same language as the student's question unless
the student explicitly requests another language.

Give 5 questions.

Use a mixture of:
- Multiple-choice questions
- Short-answer questions

After the questions, provide an answer key separately.
"""


    elif study_mode == "doubt":

        instruction = """
Answer the student's doubt clearly.

Reply in the same language as the student's question unless
the student explicitly requests another language.

Explain the concept step by step.

Use:
- Simple language
- Clear explanations
- Examples when useful

Make sure the student can understand the reason behind the answer.
"""


    else:

        instruction = """
Help the student understand the topic clearly.

Reply in the same language as the student's question unless
the student explicitly requests another language.
"""


    # Get previous conversation
    conversation = session.get("conversation", [])

    # Make sure conversation exists
    if not conversation:

        conversation = [
            {
                "role": "system",
                "content": system_instruction
            }
        ]


    # Add current study mode instruction
    conversation.append(
        {
            "role": "system",
            "content": instruction
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

        # Send conversation to Groq AI
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=conversation
        )

        # Get AI answer
        answer = response.choices[0].message.content


    except Exception as error:

        answer = (
            "Sorry, I could not generate a response right now. "
            "Please try again."
        )

        print("Groq Error:", error)


    # Add AI response to conversation history
    conversation.append(
        {
            "role": "assistant",
            "content": answer
        }
    )


    # Save updated conversation
    session["conversation"] = conversation
    session.modified = True


    # Display answer
    return render_template(
        "index.html",
        question=user_question,
        answer=answer,
        selected_mode=study_mode
    )


@app.route("/clear")
def clear():

    # Remove old conversation
    session.pop("conversation", None)

    # Create a fresh conversation
    session["conversation"] = [
        {
            "role": "system",
            "content": system_instruction
        }
    ]

    session.modified = True

    return render_template(
        "index.html",
        answer=None
    )


if __name__ == "__main__":
    app.run(debug=True)
