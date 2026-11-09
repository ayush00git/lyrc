import unittest

from lyrics_overlay.metadata import clean

CHROME = "org.mpris.MediaPlayer2.chromium.instance42"
SPOTIFY = "org.mpris.MediaPlayer2.spotify"


class TestClean(unittest.TestCase):
    def check(self, artist, title, expected, player=CHROME, album=""):
        self.assertEqual(clean(player, artist, title, album), expected)

    def test_youtube(self):
        cases = [
            ("RickAstleyVEVO", "Rick Astley - Never Gonna Give You Up (Official Video) [4K]",
             ("Rick Astley", "Never Gonna Give You Up")),
            ("Darude - Topic", "Sandstorm", ("Darude", "Sandstorm")),
            ("Some Uploader", "Queen – Bohemian Rhapsody (Official Video Remastered)",
             ("Queen", "Bohemian Rhapsody")),
            ("ColdplayVEVO", "Coldplay - Yellow (Official Video)", ("Coldplay", "Yellow")),
            ("Ed Sheeran", "Ed Sheeran - Perfect (Official Music Video)", ("Ed Sheeran", "Perfect")),
            ("Daft Punk", "Get Lucky (feat. Pharrell Williams) [Official Audio]",
             ("Daft Punk", "Get Lucky")),
            ("Lyrics Channel", "The Weeknd - Blinding Lights (Lyrics)", ("The Weeknd", "Blinding Lights")),
            ("TaylorSwiftVEVO", "Taylor Swift - Anti-Hero (Official Music Video)",
             ("Taylor Swift", "Anti-Hero")),
            ("Nirvana", "Nirvana - Smells Like Teen Spirit (Official Music Video) | HD",
             ("Nirvana", "Smells Like Teen Spirit")),
            ("Eminem", "Eminem - Lose Yourself [HD]", ("Eminem", "Lose Yourself")),
            ("Some Band", "Song Name - Live", ("Some Band", "Song Name - Live")),
            ("Artist Official", "Track", ("Artist", "Track")),
            ("Uploader", 'Adele - "Hello"', ("Adele", "Hello")),
            ("Uploader", "Drake ft. Rihanna - Take Care", ("Drake", "Take Care")),
        ]
        for artist, title, expected in cases:
            with self.subTest(title=title):
                self.check(artist, title, expected)

    def test_clean_sources_pass_through(self):
        self.check("Queen", "Bohemian Rhapsody - Remastered 2011",
                   ("Queen", "Bohemian Rhapsody - Remastered 2011"), player=SPOTIFY)
        # YT Music in Chrome provides an album.
        self.check("Daft Punk", "Get Lucky (feat. Pharrell Williams)",
                   ("Daft Punk", "Get Lucky (feat. Pharrell Williams)"), album="Random Access Memories")


if __name__ == "__main__":
    unittest.main()
