"""Memory grid operations for the flet UI.

Pure data-layer helpers (no GUI dependencies) implementing the same
semantics as the CHIRP-next wxui editor: delete with optional shift,
insert row above (shift down), move up/down and cross-model paste via
the official import engine (import_logic.import_mem).
"""

import logging

from mychirp import chirp_common
from mychirp import import_logic
from mychirp import errors as chirp_errors

LOG = logging.getLogger(__name__)


class MemoryOpError(Exception):
    """Raised when an operation cannot be safely performed."""


def _bounds(radio):
    lo, hi = radio.get_features().memory_bounds
    return lo, hi


def delete_memories(radio, numbers, shift=None):
    """Erase the given memory numbers.

    ``shift`` may be ``None`` (just erase), ``'block'`` (shift up the
    memories after the erased block until the first empty memory) or
    ``'all'`` (shift up everything after the block, mirroring the
    CHIRP "delete block+shift" / "delete all+shift" behaviors).
    """
    lo, hi = _bounds(radio)
    numbers = sorted(n for n in numbers if isinstance(n, int))
    if not numbers:
        return

    for number in numbers:
        try:
            mem = radio.get_memory(number)
            if not mem.empty:
                radio.erase_memory(number)
        except chirp_errors.RadioError:
            raise
        except Exception:
            LOG.exception("Failed to erase memory %s", number)
            raise MemoryOpError(
                "Failed to erase memory %s" % number)

    if not shift:
        return

    delta = len(numbers)
    next_number = numbers[-1] + 1
    to_move = []
    for number in range(next_number, hi + 1):
        mem = radio.get_memory(number)
        if shift == "block" and mem.empty:
            break
        to_move.append(number)

    if not to_move:
        return

    # Shift up, working from the nearest first (destinations are always
    # below the current source so order is safe)
    for number in to_move:
        mem = radio.get_memory(number).dupe()
        mem.number = number - delta
        try:
            if mem.empty:
                radio.erase_memory(mem.number)
            else:
                radio.set_memory(mem)
        except chirp_errors.RadioError as e:
            raise MemoryOpError(str(e))

    # Erase the hole left at the tail
    hole_start = to_move[-1] - delta + 1
    for number in range(max(lo, hole_start), to_move[-1] + 1):
        try:
            radio.erase_memory(number)
        except Exception:
            LOG.debug("Erase tail %s failed (ok)", number)


def insert_memories(radio, at_number, count=1):
    """Open ``count`` empty slots at ``at_number`` shifting the
    following memories down (the CHIRP "insert row above" behavior).
    Refuses to proceed if non-empty data would fall off the end.
    """
    lo, hi = _bounds(radio)
    at_number = int(at_number)
    if at_number < lo or at_number > hi:
        raise MemoryOpError("Position out of range")

    # Guard: the tail memories we would push beyond the bounds must be
    # empty, otherwise the insert would silently destroy data
    for number in range(hi - count + 1, hi + 1):
        mem = radio.get_memory(number)
        if not mem.empty:
            raise MemoryOpError(
                "Cannot insert: memory %i is not empty and would be "
                "pushed out of the radio bounds" % number)

    # Shift down, working from the end so we never overwrite unread data
    for number in range(hi - count, at_number - 1, -1):
        mem = radio.get_memory(number).dupe()
        mem.number = number + count
        try:
            if mem.empty:
                radio.erase_memory(mem.number)
            else:
                radio.set_memory(mem)
        except chirp_errors.RadioError as e:
            raise MemoryOpError(str(e))

    for number in range(at_number, at_number + count):
        radio.erase_memory(number)


def move_memory(radio, number, delta):
    """Swap a memory with an adjacent one (delta = -1 up / +1 down)."""
    lo, hi = _bounds(radio)
    number = int(number)
    other = number + delta
    if other < lo or other > hi:
        raise MemoryOpError("Cannot move beyond the radio bounds")

    mem_a = radio.get_memory(number).dupe()
    mem_b = radio.get_memory(other).dupe()
    mem_a.number, mem_b.number = other, number
    try:
        if mem_a.empty:
            radio.erase_memory(other)
        else:
            radio.set_memory(mem_a)
        if mem_b.empty:
            radio.erase_memory(number)
        else:
            radio.set_memory(mem_b)
    except chirp_errors.RadioError as e:
        raise MemoryOpError(str(e))


def paste_memory(radio, src_mem, src_features, dst_number):
    """Paste a memory into @dst_number using the CHIRP cross-model
    import engine (import_logic.import_mem), which adapts frequency
    steps, tones, power, duplex and validates against the destination
    radio's own rules."""
    dst_number = int(dst_number)
    if isinstance(dst_number, bool) or isinstance(dst_number, str):
        raise MemoryOpError("Special channels cannot be pasted onto")
    try:
        dst_mem = import_logic.import_mem(
            radio, src_features, src_mem,
            overrides={"number": dst_number, "empty": False})
    except import_logic.DestNotCompatible as e:
        raise MemoryOpError(str(e))
    except import_logic.ImportError as e:
        raise MemoryOpError(str(e))
    try:
        radio.set_memory(dst_mem)
    except chirp_errors.RadioError as e:
        raise MemoryOpError(str(e))
    return dst_mem


def export_csv(radio, filename, memories=None):
    """Export non-special memories to a CSV file.

    Mirrors the CHIRP-next wxui export: a Generic CSV radio holding
    every non-empty, non-special memory of @radio.
    """
    from mychirp.drivers import generic_csv

    lo, hi = _bounds(radio)
    max_memory = hi
    csv_radio = generic_csv.CSVRadio(None, max_memory=max_memory)
    # The CSV driver defaults to a single non-empty memory at location
    # zero, so delete it before we go to export (same as CHIRP).
    csv_radio.erase_memory(0)

    count = 0
    for number in range(lo, hi + 1):
        if memories is not None and number not in memories:
            continue
        mem = radio.get_memory(number)
        if mem.empty or not isinstance(mem.number, int) or mem.number < 0:
            # We don't export specials
            continue
        csv_radio.set_memory(mem)
        count += 1

    if count:
        csv_radio.save(filename)
    return count
