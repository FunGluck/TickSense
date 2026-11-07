"""Offline validation tests; these do not start Minecraft or accept EULA."""
import csv
from pathlib import Path
import tempfile
import unittest
from paper_compatibility import FIELDS, validate_csv, accepted, digest, compatibility_root


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        directory=self.root/'plugins/TickSense/data'
        directory.mkdir(parents=True)
        self.path=directory/'metrics-v2-2026-11-03.csv'

    def write(self,rows):
        with self.path.open('w',encoding='utf-8',newline='') as output:
            writer=csv.writer(output);writer.writerow(FIELDS);writer.writerows(rows)

    def row(self):
        return ['2026-11-03T00:00:00Z',10000,20,0,0,100,10,0,0,200,-1,-1]

    def test_valid_initial_zero_mspt_and_unavailable_gc(self):
        self.write([self.row()])
        self.assertEqual(len(validate_csv(self.root)[1]),1)

    def test_java_nanosecond_timestamp_is_valid(self):
        row=self.row();row[0]='2026-11-02T19:31:46.304499200Z';self.write([row])
        self.assertEqual(validate_csv(self.root)[1][0]['timestamp_utc'],row[0])

    def test_invalid_negative_and_wrong_type(self):
        for column,value in [(6,-1),(10,-2),(4,'player'),(3,'nan')]:
            row=self.row();row[column]=value;self.write([row])
            with self.assertRaises(ValueError):validate_csv(self.root)

    def test_duplicate_header_and_partial_tail(self):
        self.write([self.row(),FIELDS])
        with self.assertRaises(ValueError):validate_csv(self.root)
        self.path.write_text(','.join(FIELDS)+'\npartial',encoding='utf-8')
        with self.assertRaises(ValueError):validate_csv(self.root)

    def test_eula_missing_or_false_never_written(self):
        self.assertFalse(accepted(self.root))
        self.assertFalse((self.root/'eula.txt').exists())
        (self.root/'eula.txt').write_text('eula=false\n')
        self.assertFalse(accepted(self.root))
        self.assertEqual((self.root/'eula.txt').read_text(),'eula=false\n')

    def test_sha256(self):
        self.path.write_bytes(b'abc')
        self.assertEqual(digest(self.path),'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

    def test_compatibility_root_checkout_layouts(self):
        repo = self.root/'TickSense'
        expected = self.root/'TickSense-Compatibility'
        self.assertEqual(compatibility_root(repo), expected)
        self.assertEqual(compatibility_root(repo/'TickSense'), expected)

    def test_workdir_override_must_be_external(self):
        repo = self.root/'TickSense'
        custom = self.root/'other directory'
        self.assertEqual(compatibility_root(repo, custom), custom)
        for path in [repo, repo/'.gradle/compat26']:
            with self.assertRaises(ValueError):
                compatibility_root(repo, path)


if __name__=='__main__': unittest.main()
