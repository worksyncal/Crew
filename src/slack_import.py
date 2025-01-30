import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SLACK_BOT_TOKEN = os.getenv("xoxb-8323563814688-8368903217221-QZPpE68kNL0K8yflXbLwchyH")
client = WebClient(token=SLACK_BOT_TOKEN)

def send_slack_message(channel, text):
    try:
        response = client.chat_postMessage(channel=channel, text=text)
        return response
    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")

# Example: Sending a test message to Slack
send_slack_message("#general", "Hello from CrewAI!")
