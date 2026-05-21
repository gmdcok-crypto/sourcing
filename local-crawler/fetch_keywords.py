import json

from config import get_settings
from railway_client import RailwayKeywordClient


def main() -> None:
    settings = get_settings()
    client = RailwayKeywordClient(settings)
    payload = client.fetch_keywords()
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
