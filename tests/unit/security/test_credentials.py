from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.security import CredentialStore


class CredentialStoreTests(unittest.TestCase):
    def test_set_get_and_delete_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            store = CredentialStore(path)

            store.set("deepseek", "sk-test")
            self.assertEqual(store.get("deepseek"), "sk-test")
            self.assertEqual(store.get("missing"), None)

            store.delete("deepseek")
            self.assertEqual(store.get("deepseek"), None)



if __name__ == "__main__":
    unittest.main()
