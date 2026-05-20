from typing import Dict

from app.core.config import Settings


class BrightDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_configured(self) -> bool:
        return bool(
            self.settings.brightdata_browser_ws
            or (self.settings.bright_data_api_key and self.settings.bright_data_zone)
        )

    def get_status(self) -> Dict[str, bool]:
        return {
            "configured": self.is_configured(),
            "browser_api_configured": bool(self.settings.brightdata_browser_ws),
        }
