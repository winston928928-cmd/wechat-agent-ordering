import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.app.wechat_official_api import WeChatOfficialApiClient


class WeChatOfficialApiClientTests(unittest.TestCase):
    def test_reads_cached_token_without_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "token.json"
            cache_path.write_text(
                json.dumps({"access_token": "cached-token", "expires_at": 4102444800}),
                encoding="utf-8",
            )
            client = WeChatOfficialApiClient(app_id="app-id", app_secret="secret", cache_path=cache_path)
            client._http.get = Mock(side_effect=AssertionError("should not request a new token"))

            token = client._get_access_token()

            self.assertEqual(token, "cached-token")

    def test_fetches_and_caches_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "token.json"
            client = WeChatOfficialApiClient(app_id="app-id", app_secret="secret", cache_path=cache_path)

            response = Mock()
            response.json.return_value = {"access_token": "fresh-token", "expires_in": 7200}
            client._http.get = Mock(return_value=response)

            token = client._get_access_token(force_refresh=True)

            self.assertEqual(token, "fresh-token")
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(cached["access_token"], "fresh-token")

    def test_send_text_message_refreshes_expired_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "token.json"
            client = WeChatOfficialApiClient(app_id="app-id", app_secret="secret", cache_path=cache_path)
            client._get_access_token = Mock(side_effect=["old-token", "new-token"])

            first = Mock()
            first.json.return_value = {"errcode": 40001, "errmsg": "invalid credential"}
            second = Mock()
            second.json.return_value = {"errcode": 0, "errmsg": "ok"}
            client._http.post = Mock(side_effect=[first, second])

            client.send_text_message(open_id="openid-1", content="你好")

            self.assertEqual(client._http.post.call_count, 2)
            first_url = client._http.post.call_args_list[0].args[0]
            second_url = client._http.post.call_args_list[1].args[0]
            self.assertIn("old-token", first_url)
            self.assertIn("new-token", second_url)


if __name__ == "__main__":
    unittest.main()
