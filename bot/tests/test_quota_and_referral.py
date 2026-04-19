import os
import tempfile
import unittest

try:
    from bot.config.settings import config
    from bot.models.database import (
        init_db,
        ensure_user,
        apply_referral_if_new_user,
        get_referral_bonus_gb,
        get_user_daily_quota_bytes,
        consume_bytes,
        can_consume,
        get_user_used_bytes_today,
    )
except Exception:
    config = None


@unittest.skipIf(config is None, "Bot dependencies are not installed in this environment")
class TestQuotaAndReferral(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._old_db_path = config.db_path
        self._old_free = getattr(config, "free_daily_quota_gb", 10)
        self._old_premium = getattr(config, "premium_daily_quota_gb", 50)
        self._old_bonus = getattr(config, "referral_bonus_gb", 1)
        self._old_tz = getattr(config, "quota_timezone", "Asia/Tehran")

        self._td = tempfile.TemporaryDirectory()
        config.db_path = os.path.join(self._td.name, "test.db")
        config.free_daily_quota_gb = 10
        config.premium_daily_quota_gb = 50
        config.referral_bonus_gb = 1
        config.quota_timezone = "Asia/Tehran"
        await init_db()

    async def asyncTearDown(self):
        config.db_path = self._old_db_path
        config.free_daily_quota_gb = self._old_free
        config.premium_daily_quota_gb = self._old_premium
        config.referral_bonus_gb = self._old_bonus
        config.quota_timezone = self._old_tz
        self._td.cleanup()

    async def test_quota_consumption(self):
        uid = 100
        await ensure_user(uid, "u")
        limit = await get_user_daily_quota_bytes(uid)
        self.assertEqual(limit, 10 * 1024 * 1024 * 1024)

        await consume_bytes(uid, 90 * 1024 * 1024)
        used = await get_user_used_bytes_today(uid)
        self.assertEqual(used, 90 * 1024 * 1024)

        ok, _, _ = await can_consume(uid, limit - used)
        self.assertTrue(ok)

        ok, _, _ = await can_consume(uid, limit - used + 1)
        self.assertFalse(ok)

    async def test_referral_bonus_increases_daily_quota(self):
        referrer = 200
        new_user = 201
        await ensure_user(referrer, "ref")
        await ensure_user(new_user, "new")

        ok = await apply_referral_if_new_user(new_user, referrer)
        self.assertTrue(ok)
        bonus = await get_referral_bonus_gb(referrer)
        self.assertEqual(bonus, 1)

        limit = await get_user_daily_quota_bytes(referrer)
        self.assertEqual(limit, 11 * 1024 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
