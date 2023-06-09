import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def send_telegram_message(message: str) -> None:
    auth_file = Path(__file__).parent.parent / "credentials/telegram auth.json"
    auth_json = json.loads(auth_file.read_text())
    bot_token = auth_json["token"]
    chat_id = auth_json["chat_id"]
    api_url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {'chat_id': chat_id, 'text': message}
    try:
        response = requests.post(api_url, data=data)
        response.raise_for_status()
        logger.debug(f"Telegram message sent. Response: {response.text}")
    except Exception as error:
        logger.exception(f"An error occurred while sending message to telegram bot! Error: {error}")


if __name__ == '__main__':
    test_message = "This is a test message."
    send_telegram_message(test_message)
