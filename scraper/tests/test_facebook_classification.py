from __future__ import annotations

import unittest

from scraper.facebook.facebook_marketplace import extract_category


class FacebookClassificationTests(unittest.TestCase):
    def test_laptop_family_terms_beat_gpu_terms(self):
        self.assertEqual(
            extract_category("ASUS TUF F15 RTX 3050 i5 fullset gaming mulus"),
            "Laptop",
        )
        self.assertEqual(
            extract_category("MSI GF63 Thin RTX 4060 murah Jakarta"),
            "Laptop",
        )
        self.assertEqual(
            extract_category("ROG Strix G15 RTX 3060 RAM 16 SSD 512"),
            "Laptop",
        )

    def test_gpu_only_listing_still_classifies_as_gpu(self):
        self.assertEqual(extract_category("VGA RTX 3060 Ti 8GB bekas"), "GPU")

    def test_staging_laptop_families_beat_component_terms(self):
        self.assertEqual(
            extract_category("Dell latitude 3490 ultraslim core i5 Gen7 ram4 hdd500 siap pakai"),
            "Laptop",
        )
        self.assertEqual(
            extract_category("Acer Aspire 3 A315-42 AMD Ryzen 3 3200U Radeon Vega 3 2GB"),
            "Laptop",
        )

    def test_staging_complete_pc_beats_ram_and_cpu_terms(self):
        self.assertEqual(
            extract_category("PC intel 64core dual e5 2698v3 ram 64gb ddr4 ssd nvme"),
            "Desktop PC",
        )


if __name__ == "__main__":
    unittest.main()
