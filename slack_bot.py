from flask import Flask, request, jsonify, redirect
from slack_sdk import WebClient
import os

# Load Slack Tokens from Environment Variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Initialize Slack WebClient
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Flask App
app = Flask(__name__)

@app.route("/")
def home():
    return "CrewAI Slack Bot is running!"

# ✅ Fix: Ensure Slack's event endpoint allows POST requests
@app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handles Slack event subscriptions, including challenge verification"""
    data = request.get_json()

    # ✅ Respond to Slack's challenge request
    if data.get("type") == "url_verification":
        return data["challenge"], 200, {"Content-Type": "text/plain"}

    # ✅ Handle Slack messages
    if "event" in data:
        event = data["event"]

        # Only process user messages (ignore bot messages)
        if event.get("type") == "message" and "subtype" not in event:
            channel = event.get("channel")
            user_message = event.get("text")

            # Process message with AI (Replace this with CrewAI logic)
            response_text = f"Hello! You said: {user_message}"

            # Send response to Slack
            send_message(channel, response_text)

    return jsonify({"status": "ok"}), 200

# ✅ Handle Slack OAuth Redirect
@app.route("/slack/oauth_redirect")
def slack_oauth_redirect():
    """Handles Slack OAuth Authentication"""
    code = request.args.get("code")
    if not code:
        return "Error: No code provided!", 400

    # Exchange code for access token
    response = slack_client.oauth_v2_access(
        client_id=SLACK_CLIENT_ID,
        client_secret=SLACK_CLIENT_SECRET,
        code=code
    )

    if response["ok"]:
        return "Slack OAuth successful! You can close this window."
    else:
        return f"Error: {response['error']}", 400

def send_message(channel, text):
    """Sends a message to Slack"""
    try:
        slack_client.chat_postMessage(channel=channel, text=text)
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

