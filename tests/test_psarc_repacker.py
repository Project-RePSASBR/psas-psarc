from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from psas_psarc.psarc_extractor import _PsarcExtractor, extract_psas_psarc
from psas_psarc.psarc_repacker import repack_psas_psarc


class PsarcRepackerTestCase(unittest.TestCase):
    def test_repacked_archive_matches_sample(self) -> None:
        root = Path(__file__).resolve().parents[1]
        sample_path = root / "sample_psarcs" / "ps3" / "patch.psarc"
        original = _PsarcExtractor(sample_path)

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            extract_dir = tmp_dir / "extracted"
            extract_dir.mkdir()
            extract_psas_psarc(sample_path, extract_dir)
            source_dir = extract_dir / sample_path.stem

            output_path = tmp_dir / "repacked.psarc"
            repack_psas_psarc(source_dir, output_path, encrypt=True, file_order=original.manifest)

            repacked = _PsarcExtractor(output_path)
            self.assertEqual(original.manifest, repacked.manifest)
            for filename in original.manifest:
                self.assertEqual(original.extract_single_file(filename), repacked.extract_single_file(filename))


if __name__ == "__main__":
    unittest.main()
