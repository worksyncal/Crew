import os
import requests
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from flask import Flask

# Load Slack Tokens from Environment Variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# Initialize Slack WebClient
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Flask App for Basic Status Check
app = Flask(__name__)

@app.route("/")
def home():
    return "CrewAI Slack Bot is running in Socket Mode!"

# Open WebSocket Connection via Slack API
def open_socket_connection():
    url = "https://slack.com/api/apps.connections.open"
    headers = {"Authorization": f"Bearer {SLACK_APP_TOKEN}"}
    
    response = requests.post(url, headers=headers)
    data = response.json()

    if data.get("ok"):
        print("✅ WebSocket URL:", data["url"])
        return data["url"]
    else:
        print("❌ Failed to open WebSocket:", data)
        return None

# Event Handler for Messages
def process_message(req: SocketModeRequest):
    if req.type == "events_api":
        event = req.payload.get("event", {})

        if event.get("type") == "message" and "subtype" not in event:
            channel = event.get("channel")
            user_message = event.get("text")

            # Process the message (Replace with CrewAI logic if needed)
            response_text = f"Received: {user_message}"

            # Send the response back to Slack
            slack_client.chat_postMessage(channel=channel, text=response_text)

        # Acknowledge the event
        return SocketModeResponse(envelope_id=req.envelope_id)

# Start the WebSocket Connection
if __name__ == "__main__":
    socket_client = SocketModeClient(app_token=SLACK_APP_TOKEN, web_client=slack_client)
    socket_client.socket_mode_request_listeners.append(process_message)

    # ✅ Open WebSocket Connection
    ws_url = open_socket_connection()
    if ws_url:
        socket_client.connect()
    else:
        print("❌ WebSocket connection failed.")

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
