"""Chat with the ParkPulse bot in the terminal (no WhatsApp account needed).

    python scripts/chat_cli.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parkpulse.bot import handle_message
from parkpulse.state import LiveState


def main():
    state = LiveState(history_days=21)
    session: dict = {}
    print("ParkPulse bot. Try: 'parking near raghunath bazaar', 'गांधी नगर', '2', or 'quit'.")
    while True:
        try:
            text = input("you> ").strip()
        except EOFError:
            break
        if text.lower() in {"quit", "exit"}:
            break
        print(handle_message(state, text, session=session).text, "\n")


if __name__ == "__main__":
    main()
