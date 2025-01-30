from flask import Flask, request, jsonify
from crewai import Agent, Task, Crew
from slack_sdk import WebClient
import os

# Load Slack Bot Token
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Flask App Setup
app = Flask(__name__)

@app.route("/")
def home():
    return "CrewAI Slack Bot is running!"

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    
    # Verify Slack Challenge Request
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    # Handle Slack Message Events
    if "event" in data:
        event = data["event"]
        if event.get("type") == "message" and "subtype" not in event:
            user = event.get("user")
            text = event.get("text")
            channel = event.get("channel")

            # Respond using CrewAI
            response = crewai_process(text)
            slack_client.chat_postMessage(channel=channel, text=response)

    return jsonify({"status": "ok"})

def crewai_process(message):
    """ CrewAI processing function """
    agent = Agent(
        role="AI Assistant",
        goal="Help users by answering questions in Slack",
        verbose=True,
        memory=True,
        backstory="You are a helpful AI bot that provides great answers."
    )

    task = Task(
        description=f"Answer this Slack message: {message}",
        expected_output="A well-structured and helpful response.",
        agent=agent
    )

    crew = Crew(agents=[agent], tasks=[task])
    return crew.kickoff()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
