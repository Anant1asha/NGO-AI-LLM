import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from aasha.orchestrator.g95_peer_arena_challenge import (  # noqa: E402
    create_offline_peer_arena_challenge,
)


class TestG95PeerArenaChallenge(unittest.TestCase):
    def test_creates_offline_peer_arena_challenge_invite(self):
        res = create_offline_peer_arena_challenge(
            "STU-G95-01",
            "SCI_CH08",
            "GENRE-PHY-MATTERJS-LAB",
            88.0,
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["offline_only"])
        self.assertTrue(res["zero_external_urls"])
        self.assertTrue(res["invite_code"].startswith("ARENA-"))
        self.assertGreater(len(res["challenge_sha256"]), 32)


if __name__ == "__main__":
    unittest.main()
