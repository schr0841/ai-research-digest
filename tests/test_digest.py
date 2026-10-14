import unittest
from unittest.mock import patch
import digest


class DigestTests(unittest.TestCase):
    def test_month_rollover_and_leap_year(self):
        start, end = digest.month_bounds("2024-02")
        self.assertEqual((end - start).days, 29)
        self.assertEqual(str(digest.month_bounds("2025-12")[1]), "2026-01-01")

    def test_feed_and_versions(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:o="http://a9.com/-/spec/opensearch/1.1/"><o:totalResults>1</o:totalResults><entry><id>http://arxiv.org/abs/2609.12345v2</id><title> Useful\n paper </title><summary>Open-source benchmark</summary><published>2026-09-12T00:00:00Z</published><author><name>A Author</name></author><category term="cs.AI"/></entry></feed>'''
        papers, total = digest.parse_feed(xml)
        self.assertEqual(total, 1)
        self.assertEqual(papers[0]["id"], "2609.12345")
        self.assertEqual(papers[0]["title"], "Useful paper")

    def test_ranking_and_diversity(self):
        papers = [{"id": str(i), "title": title, "abstract": ""} for i, title in enumerate(["agent", "agent", "benchmark", "unrelated"])]
        selected = digest.rank(papers, {"top_n": 2, "weights": {"agent": 3, "benchmark": 2}})
        self.assertEqual([p["title"] for p in selected], ["agent", "benchmark"])

    def test_duplicate_issue_is_not_republished(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test", "GITHUB_REPOSITORY": "owner/repo"}), patch("digest.request", return_value=b'[{"title":"AI research digest \\u2014 2026-09","html_url":"https://example.org"}]') as req:
            digest.publish_issue("2026-09", "body")
            self.assertEqual(req.call_count, 1)

    def test_incomplete_feed_fails(self):
        with patch("digest.request", return_value=b""), patch("digest.parse_feed", return_value=([], 20)):
            with self.assertRaises(RuntimeError):
                digest.fetch({"categories": ["cs.AI"], "max_candidates": 100}, *digest.month_bounds("2026-09"))


if __name__ == "__main__":
    unittest.main()
