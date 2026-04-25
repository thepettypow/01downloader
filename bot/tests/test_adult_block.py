import unittest
from datetime import datetime, timedelta, timezone

try:
    from bot.config.settings import config
    from bot.handlers.download import _adult_downloads_blocked, _is_adult_site
except Exception:
    config = None


@unittest.skipIf(config is None, "Bot dependencies are not installed in this environment")
class TestAdultBlock(unittest.TestCase):
    def setUp(self):
        self._old_enabled = getattr(config, "adult_downloads_enabled", None)
        self._old_until = getattr(config, "adult_downloads_block_until", None)

    def tearDown(self):
        if self._old_enabled is not None:
            config.adult_downloads_enabled = self._old_enabled
        config.adult_downloads_block_until = self._old_until

    def test_is_adult_site(self):
        self.assertTrue(_is_adult_site("https://www.pornhub.com/view_video.php?viewkey=ph5"))
        self.assertTrue(_is_adult_site("https://m.xvideos.com/video123"))
        self.assertTrue(_is_adult_site("https://xnxx.com/video-abc"))
        self.assertFalse(_is_adult_site("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

    def test_adult_downloads_blocked_toggle(self):
        config.adult_downloads_enabled = False
        config.adult_downloads_block_until = None
        self.assertTrue(_adult_downloads_blocked())

        config.adult_downloads_enabled = True
        config.adult_downloads_block_until = None
        self.assertFalse(_adult_downloads_blocked())

        config.adult_downloads_enabled = True
        config.adult_downloads_block_until = datetime.now(timezone.utc) + timedelta(days=1)
        self.assertTrue(_adult_downloads_blocked())

        config.adult_downloads_block_until = datetime.now(timezone.utc) - timedelta(days=1)
        self.assertFalse(_adult_downloads_blocked())


if __name__ == "__main__":
    unittest.main()

