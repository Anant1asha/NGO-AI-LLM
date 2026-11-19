import unittest

from src.aasha.orchestrator.multi_genre_arena_router import (
    MULTI_GENRE_THEME_CATALOG,
    route_chapter_to_arena_genre,
)


class TestG68MultiGenreArenaRouter(unittest.TestCase):
    def test_five_distinct_genres_prevent_single_theme_monoculture(self):
        self.assertGreaterEqual(len(MULTI_GENRE_THEME_CATALOG), 5)
        sci = route_chapter_to_arena_genre("NCERT-G08-SCI-CH08", "science")
        math = route_chapter_to_arena_genre("NCERT-G06-MATH-CH07", "math")
        voc = route_chapter_to_arena_genre("NCVET-G09-PLUMB-CH01", "vocational")
        soc = route_chapter_to_arena_genre("NCERT-G09-SOC-PALAMPUR", "social_science")
        sport = route_chapter_to_arena_genre("Class8_Science_Cricket", "sports_stem")

        themes = {sci["theme_name"], math["theme_name"], voc["theme_name"], soc["theme_name"], sport["theme_name"]}
        self.assertEqual(len(themes), 5)
        for item in (sci, math, voc, soc, sport):
            self.assertTrue(item["single_theme_monoculture_disabled"])
            self.assertTrue(item["includes_finger_scratchpad"])


if __name__ == "__main__":
    unittest.main()
