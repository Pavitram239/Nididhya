"""Regression checks for topic references to Swamini Vato master IDs.

Run from the project root:
    python -m unittest discover -s backend/tests -p "test_topic_links.py" -v
"""

import copy
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.librarian import Librarian, librarian_service


class TopicLinkTests(unittest.TestCase):
    def test_topic_539_resolves_to_chapter_three_vat_four(self):
        topics = librarian_service.get_all_topics()
        first_topic = next(topic for topic in topics if str(topic["id"]) == "1")
        references = {str(vat["id"]): vat for vat in first_topic["linked_vats"]}

        self.assertEqual(
            (references["539"]["prakran_no"], references["539"]["vat_no"]),
            (3, 4),
        )
        self.assertEqual(
            (references["162"]["prakran_no"], references["162"]["vat_no"]),
            (1, 162),
        )

    def test_every_corpus_reference_matches_its_master_entry(self):
        masters = {
            str(vat["id"]): vat for vat in librarian_service.swamini_vato_data
        }
        topics = librarian_service.get_all_topics()
        reference_count = 0

        for topic in topics:
            self.assertEqual(len(topic["linked_vats"]), len(topic["linked_vat_ids"]))
            for source_id, reference in zip(topic["linked_vat_ids"], topic["linked_vats"]):
                with self.subTest(topic=topic["id"], master_id=source_id):
                    expected = masters[str(source_id)]
                    self.assertEqual(str(reference["id"]), str(source_id))
                    self.assertEqual(reference["prakran_no"], expected["prakran_no"])
                    self.assertEqual(reference["vat_no"], expected["vat_no"])
                    resolved = librarian_service.get_swaminivato_vat(
                        reference["prakran_no"], reference["vat_no"]
                    )
                    self.assertEqual(str(resolved["id"]), str(source_id))
                    reference_count += 1

        self.assertGreater(reference_count, 0)

    def test_numeric_and_string_ids_resolve_consistently(self):
        service = self.make_service(
            masters=[
                {"id": 539, "prakran_no": 3, "vat_no": 4},
                {"id": "162", "prakran_no": 1, "vat_no": 162},
            ],
            linked_ids=["539", 162],
        )

        references = service.get_all_topics()[0]["linked_vats"]

        self.assertEqual(
            [(vat["prakran_no"], vat["vat_no"]) for vat in references],
            [(3, 4), (1, 162)],
        )

    def test_missing_id_is_unresolved_instead_of_using_first_vat(self):
        service = self.make_service(
            masters=[{"id": 1, "prakran_no": 1, "vat_no": 1}],
            linked_ids=[999999],
        )

        reference = service.get_all_topics()[0]["linked_vats"][0]

        self.assertEqual(str(reference["id"]), "999999")
        self.assertIsNone(reference["prakran_no"])
        self.assertIsNone(reference["vat_no"])

    def test_enrichment_preserves_original_topic_data(self):
        service = self.make_service(
            masters=[{"id": 539, "prakran_no": 3, "vat_no": 4}],
            linked_ids=[539],
        )
        original_topics = copy.deepcopy(service.topics_data)

        result = service.get_all_topics()

        self.assertEqual(service.topics_data, original_topics)
        self.assertEqual(result[0]["linked_vat_ids"], original_topics[0]["linked_vat_ids"])
        self.assertNotIn("linked_vats", service.topics_data[0])

    @staticmethod
    def make_service(masters, linked_ids):
        service = Librarian.__new__(Librarian)
        service.swamini_vato_data = masters
        service.topics_data = [
            {"id": "test-topic", "name_en": "Test topic", "linked_vat_ids": linked_ids}
        ]
        return service


if __name__ == "__main__":
    unittest.main()
