"""Tests for the memory operations (data-layer, mock-free).

Uses real file-backed radios from tests/images so every operation is
exercised against the actual driver code paths (no GUI involved).
"""

import os
import shutil
import tempfile
import unittest

from mychirp import chirp_common
from mychirp import directory
from mychirp import settings as chirp_settings
from mychirp import memory_ops

directory.import_drivers()

IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "images")
UV5R = os.path.join(IMG_DIR, "Baofeng_UV-5R.img")
IC2820 = os.path.join(IMG_DIR, "Icom_IC-2820H.img")


def make_mem(number, name, freq=146520000):
    mem = chirp_common.Memory()
    mem.number = number
    mem.freq = freq
    mem.name = name
    mem.mode = "FM"
    mem.tuning_step = 5.0
    return mem


def name_at(radio, number):
    return radio.get_memory(number).name


class TestDeleteMemories(unittest.TestCase):
    def setUp(self):
        self.radio = directory.get_radio_by_image(UV5R)
        for i in range(1, 9):
            self.radio.set_memory(make_mem(i, "T%i" % i))

    def test_delete_single(self):
        memory_ops.delete_memories(self.radio, [1])
        self.assertTrue(self.radio.get_memory(1).empty)
        # everything else untouched
        self.assertEqual(name_at(self.radio, 2), "T2")

    def test_delete_block_shift(self):
        # channel 5 is the first of a block 5..8; 9+ is empty
        memory_ops.delete_memories(self.radio, [5], shift="block")
        self.assertEqual(name_at(self.radio, 5), "T6")
        self.assertEqual(name_at(self.radio, 6), "T7")
        self.assertEqual(name_at(self.radio, 7), "T8")
        self.assertTrue(self.radio.get_memory(8).empty)
        self.assertEqual(name_at(self.radio, 1), "T1")

    def test_delete_all_shift(self):
        memory_ops.delete_memories(self.radio, [1], shift="all")
        self.assertEqual(name_at(self.radio, 1), "T2")
        self.assertEqual(name_at(self.radio, 7), "T8")
        self.assertTrue(self.radio.get_memory(8).empty)

    def test_delete_special_ignored(self):
        # str numbers (specials) must be ignored, not crash
        memory_ops.delete_memories(self.radio, ["foo"])


class TestInsertMemories(unittest.TestCase):
    def setUp(self):
        self.radio = directory.get_radio_by_image(UV5R)
        # the stock image has programmed channels (incl. the last one);
        # clear the tail so insert has room to shift into
        hi = self.radio.get_features().memory_bounds[1]
        for i in range(0, hi + 1):
            if not self.radio.get_memory(i).empty:
                self.radio.erase_memory(i)
        for i in range(0, 5):
            self.radio.set_memory(make_mem(i, "T%i" % i))

    def test_insert_above(self):
        memory_ops.insert_memories(self.radio, 2)
        self.assertTrue(self.radio.get_memory(2).empty)
        self.assertEqual(name_at(self.radio, 3), "T2")
        self.assertEqual(name_at(self.radio, 4), "T3")
        self.assertEqual(name_at(self.radio, 5), "T4")
        # 0..1 untouched
        self.assertEqual(name_at(self.radio, 1), "T1")

    def test_insert_refuses_when_tail_full(self):
        # fill the very last channel: inserting would push it out
        hi = self.radio.get_features().memory_bounds[1]
        self.radio.set_memory(make_mem(hi, "EDGE"))
        with self.assertRaises(memory_ops.MemoryOpError):
            memory_ops.insert_memories(self.radio, 0)

    def test_insert_out_of_range(self):
        with self.assertRaises(memory_ops.MemoryOpError):
            memory_ops.insert_memories(self.radio, 9999)


class TestMoveMemory(unittest.TestCase):
    def setUp(self):
        self.radio = directory.get_radio_by_image(UV5R)
        self.radio.set_memory(make_mem(10, "A"))
        self.radio.set_memory(make_mem(11, "B"))

    def test_move_down(self):
        memory_ops.move_memory(self.radio, 10, +1)
        self.assertEqual(name_at(self.radio, 10), "B")
        self.assertEqual(name_at(self.radio, 11), "A")

    def test_move_up(self):
        memory_ops.move_memory(self.radio, 11, -1)
        self.assertEqual(name_at(self.radio, 10), "B")
        self.assertEqual(name_at(self.radio, 11), "A")

    def test_move_beyond_bounds(self):
        hi = self.radio.get_features().memory_bounds[1]
        self.radio.set_memory(make_mem(hi, "LAST"))
        with self.assertRaises(memory_ops.MemoryOpError):
            memory_ops.move_memory(self.radio, hi, +1)


class TestPasteMemory(unittest.TestCase):
    def setUp(self):
        self.radio = directory.get_radio_by_image(UV5R)

    def test_paste_same_radio(self):
        src = make_mem(1, "SOURCE", freq=146550000)
        src.rtone = 100.0
        src.tmode = "Tone"
        self.radio.set_memory(src)
        self.radio.set_memory(make_mem(60, "OLD"))

        pasted = memory_ops.paste_memory(
            self.radio, src, self.radio.get_features(), 60)
        self.assertEqual(pasted.number, 60)
        self.assertEqual(name_at(self.radio, 60), "SOURCE")
        self.assertEqual(
            self.radio.get_memory(60).freq, 146550000)

    def test_paste_cross_model(self):
        """The CHIRP parity feature: paste a Baofeng memory into an
        Icom IC-2820H using the official import engine."""
        src_radio = directory.get_radio_by_image(UV5R)
        src_radio.set_memory(make_mem(1, "XMODEL", freq=146520000))
        src_mem = src_radio.get_memory(1)
        src_features = src_radio.get_features()

        dst = directory.get_radio_by_image(IC2820)
        dst.set_memory(make_mem(100, "OLD"))
        pasted = memory_ops.paste_memory(
            dst, src_mem, src_features, 100)
        self.assertEqual(pasted.number, 100)
        self.assertEqual(dst.get_memory(100).freq, 146520000)
        self.assertEqual(name_at(dst, 100), "XMODEL")

    def test_paste_incompatible_rejected(self):
        """Frequencies outside the destination bands must be refused
        by the import engine, not written to the radio."""
        src_radio = directory.get_radio_by_image(UV5R)
        out_of_band = make_mem(1, "OOB", freq=1000)  # 1 kHz: invalid
        dst = directory.get_radio_by_image(IC2820)
        with self.assertRaises(memory_ops.MemoryOpError):
            memory_ops.paste_memory(
                dst, out_of_band, src_radio.get_features(), 100)


class TestExportCsv(unittest.TestCase):
    def setUp(self):
        self.radio = directory.get_radio_by_image(UV5R)
        # start from a clean slate so counts are deterministic
        hi = self.radio.get_features().memory_bounds[1]
        for i in range(0, hi + 1):
            if not self.radio.get_memory(i).empty:
                self.radio.erase_memory(i)
        self.radio.set_memory(make_mem(1, "ONE"))
        self.radio.set_memory(make_mem(2, "TWO"))

    def test_export_reimport_roundtrip(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "export.csv")

        count = memory_ops.export_csv(self.radio, path)
        self.assertEqual(count, 2)

        reopened = directory.get_radio_by_image(path)
        self.assertEqual(name_at(reopened, 1), "ONE")
        self.assertEqual(name_at(reopened, 2), "TWO")
        self.assertEqual(reopened.get_memory(2).freq, 146520000)

    def test_export_empty_radio(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        radio = directory.get_radio_by_image(UV5R)
        hi = radio.get_features().memory_bounds[1]
        for i in range(0, hi + 1):
            if not radio.get_memory(i).empty:
                radio.erase_memory(i)
        path = os.path.join(tmp, "empty.csv")
        count = memory_ops.export_csv(radio, path)
        self.assertEqual(count, 0)
        self.assertFalse(os.path.exists(path))


class TestBanksDataLayer(unittest.TestCase):
    """Verifies the BankModel plumbing the Banks screen relies on,
    using the Icom IC-2820H image (has_bank=True)."""

    def setUp(self):
        self.radio = directory.get_radio_by_image(IC2820)
        self.assertTrue(self.radio.get_features().has_bank)
        self.model = self.radio.get_bank_model()

    def test_list_banks(self):
        banks = list(self.model.get_mappings())
        self.assertTrue(banks)
        for bank in banks:
            # bank names may legitimately be blank on a real radio
            # (e.g. '' until the user names them); index must exist
            self.assertIsNotNone(bank.get_index())

    def test_add_remove_membership(self):
        banks = list(self.model.get_mappings())
        bank = banks[0]
        mem = make_mem(1, "BANKT")
        self.radio.set_memory(mem)

        self.model.add_memory_to_mapping(mem, bank)
        members = [b.get_index()
                   for b in self.model.get_memory_mappings(mem)]
        self.assertIn(bank.get_index(), members)

        self.model.remove_memory_from_mapping(mem, bank)
        members = [b.get_index()
                   for b in self.model.get_memory_mappings(mem)]
        self.assertNotIn(bank.get_index(), members)


if __name__ == "__main__":
    unittest.main()
