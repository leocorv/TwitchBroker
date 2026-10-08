"""JSONL replay harness; synthetic timestamps make runs reproducible."""
import json
import sys
from .control import Engine


def main():
    engine = Engine()
    for line in sys.stdin:
        event = json.loads(line)
        now = event["at"]
        kind = event["type"]
        if kind == "message":
            engine.ingest(event["user"], event["id"], event["text"], now)
        elif kind == "reset":
            engine.reset()
            print(json.dumps({"at": now, **engine.tick(now)}))
        elif kind == "tick":
            print(json.dumps({"at": now, **engine.tick(now)}))
        else:
            raise ValueError(f"Unknown event type: {kind}")


if __name__ == "__main__":
    main()
