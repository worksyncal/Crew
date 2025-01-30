from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os

from crewai import Agent, Task, Crew

# Load Slack Bot Token from Heroku Environment Variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Flask App to Handle Slack Requests
app = Flask(__name__)

@app.route("/")
def home():
    return "CrewAI Slack Bot is running!"

@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handles Slack event subscriptions, including challenge verification"""
    data = request.get_json()

    # ✅ Fix: Respond to Slack's challenge request in the exact format required
    if data.get("type") == "url_verification":
        return data["challenge"], 200, {"Content-Type": "text/plain"}

    # Process Slack Messages
    if "event" in data:
        event = data["event"]

        # Only process user messages (ignore bot messages)
        if event.get("type") == "message" and "subtype" not in event:
            channel = event.get("channel")
            user_message = event.get("text")

            # Process message with CrewAI
            bot_response = process_with_crewai(user_message)

            # Send response back to Slack
            send_message(channel, bot_response)

    return jsonify({"status": "ok"}), 200

def process_with_crewai(message):
    """Processes the Slack message using CrewAI"""
    agent = Agent(
        role="AI Assistant",
        goal="Help users by answering questions in Slack",
        verbose=True,
        memory=True,
        backstory="You are a helpful AI bot that provides intelligent answers."
    )

    task = Task(
        description=f"Generate a helpful response to this message: {message}",
        expected_output="A well-structured and informative response.",
        agent=agent
    )

    crew = Crew(agents=[agent], tasks=[task])
    return crew.kickoff()

def send_message(channel, text):
    """Sends a message to Slack"""
    try:
        slack_client.chat_postMessage(channel=channel, text=text)
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

