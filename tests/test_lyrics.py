import unittest

from lyrics_overlay.lyrics import parse_lrc, pick_best, word_timeline


class TestLrc(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_lrc("[00:01.50]a\n[01:02.00]b"), [(1.5, "a"), (62.0, "b")])

    def test_multi_stamp_and_tags(self):
        text = "[ar:Someone]\n[00:10.00][00:30.00]chorus\n[00:20]verse\n[00:25.00]\n"
        self.assertEqual(parse_lrc(text),
                         [(10.0, "chorus"), (20.0, "verse"), (25.0, ""), (30.0, "chorus")])

    def test_offset(self):
        self.assertEqual(parse_lrc("[offset:+500]\n[00:02.00]x"), [(1.5, "x")])

    def test_empty(self):
        self.assertEqual(parse_lrc(""), [])
        self.assertEqual(parse_lrc(None), [])


class TestWords(unittest.TestCase):
    def test_spread_over_line(self):
        w = word_timeline([(10.0, "hi there friend"), (20.0, "next")])
        self.assertEqual([x[1] for x in w[:3]], ["hi", "there", "friend"])
        self.assertEqual(w[0][0], 10.0)
        times = [x[0] for x in w[:3]]
        self.assertTrue(times == sorted(times) and times[2] < 10.0 + 3 * 0.42)
        self.assertIn((10.0 + 3 * 0.42 + 1.0, "♪"), [(round(t, 2), x) for t, x in w])  # gap note

    def test_fast_line_fits_before_next(self):
        w = word_timeline([(0.0, "one two three four five six"), (1.0, "x")])
        self.assertTrue(all(t < 1.0 for t, _ in w[:6]))

    def test_empty_line_is_note(self):
        self.assertEqual(word_timeline([(5.0, "")]), [(5.0, "♪")])

    def test_enhanced_lrc(self):
        lines = parse_lrc("[00:01.00]<00:01.00>a <00:01.50>b <00:02.20>c", keep_word_tags=True)
        self.assertEqual(word_timeline(lines), [(1.0, "a"), (1.5, "b"), (2.2, "c")])
        self.assertEqual(parse_lrc("[00:01.00]<00:01.00>a <00:01.50>b"), [(1.0, "a b")])


class TestPick(unittest.TestCase):
    def test_prefers_synced_and_close_duration(self):
        rs = [
            {"id": 1, "duration": 200, "plainLyrics": "p"},
            {"id": 2, "duration": 201, "plainLyrics": "p", "syncedLyrics": "[00:01]s"},
            {"id": 3, "duration": 300, "plainLyrics": "p", "syncedLyrics": "[00:01]s"},
        ]
        self.assertEqual(pick_best(rs, 200)["id"], 2)

    def test_rejects_far_duration(self):
        self.assertIsNone(pick_best([{"duration": 400, "plainLyrics": "p"}], 200))

    def test_no_duration(self):
        self.assertEqual(pick_best([{"id": 1, "plainLyrics": "p"}], 0)["id"], 1)


if __name__ == "__main__":
    unittest.main()
