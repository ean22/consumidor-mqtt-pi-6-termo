import base64
import unittest
from types import SimpleNamespace

from bridge import add_persistence_timestamp, build_document


class BuildDocumentTests(unittest.TestCase):
    def make_message(self, payload):
        return SimpleNamespace(
            payload=payload,
            topic="sensores/temperatura",
            qos=1,
            retain=False,
        )

    def test_json_payload_keeps_text_and_decoded_data(self):
        payload = b'{"temperatura": 21.5}'

        document = build_document(self.make_message(payload))

        self.assertEqual(document["payload"], payload.decode("utf-8"))
        self.assertEqual(document["payload_data"], {"temperatura": 21.5})
        self.assertEqual(document["topic"], "sensores/temperatura")
        self.assertEqual(document["qos"], 1)
        self.assertFalse(document["retain"])
        self.assertIsNotNone(document["received_at"].tzinfo)

    def test_plain_text_is_preserved_as_string_data(self):
        document = build_document(self.make_message(b"sensor online"))

        self.assertEqual(document["payload"], "sensor online")
        self.assertEqual(document["payload_data"], "sensor online")

    def test_persistence_timestamp_uses_utc(self):
        document = build_document(self.make_message(b"sensor online"))

        add_persistence_timestamp(document)

        self.assertIsNotNone(document["data"].tzinfo)
        self.assertEqual(document["data"].utcoffset().total_seconds(), 0)

    def test_binary_payload_is_base64_encoded(self):
        payload = b"\xff\x00\x80"

        document = build_document(self.make_message(payload))

        self.assertEqual(document["payload_base64"], base64.b64encode(payload).decode("ascii"))
        self.assertNotIn("payload_data", document)
        self.assertNotIn("payload", document)


if __name__ == "__main__":
    unittest.main()