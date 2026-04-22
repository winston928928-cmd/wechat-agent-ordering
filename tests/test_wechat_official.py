import unittest

from src.app.wechat_official import build_text_reply, is_subscribe_event, is_text_message, parse_message, verify_signature


class WeChatOfficialTests(unittest.TestCase):
    def test_verify_signature(self) -> None:
        self.assertFalse(
            verify_signature(
                token="testtoken",
                timestamp="1710000000",
                nonce="123456",
                signature="bad_signature",
            )
        )

        self.assertTrue(
            verify_signature(
                token="testtoken",
                timestamp="1710000000",
                nonce="123456",
                signature="0392cb241ddb850b0eed5a4e9e3a6296408ad19d",
            )
        )

    def test_parse_and_reply(self) -> None:
        xml_text = (
            "<xml>"
            "<ToUserName><![CDATA[toUser]]></ToUserName>"
            "<FromUserName><![CDATA[fromUser]]></FromUserName>"
            "<CreateTime>1348831860</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            "<Content><![CDATA[this is a test]]></Content>"
            "</xml>"
        )

        payload = parse_message(xml_text)

        self.assertEqual(payload["ToUserName"], "toUser")
        self.assertTrue(is_text_message(payload))
        self.assertFalse(is_subscribe_event(payload))

        reply = build_text_reply(to_user="fromUser", from_user="toUser", content="你好")
        self.assertIn("<MsgType><![CDATA[text]]></MsgType>", reply)
        self.assertIn("<Content><![CDATA[你好]]></Content>", reply)

    def test_subscribe_event(self) -> None:
        payload = {
            "MsgType": "event",
            "Event": "subscribe",
        }
        self.assertTrue(is_subscribe_event(payload))


if __name__ == "__main__":
    unittest.main()
