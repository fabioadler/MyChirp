#!/usr/bin/env python3
"""mychirp-fw — dump de memória de rádio via protocolo de clonagem do driver.

Usage:
    mychirp-fw --serial=/dev/ttyUSB0 --radio=BAOFENG_BF-777S
    mychirp-fw --serial=COM3 --radio=BAOFENG_UV-5R --backup
    mychirp-fw --list-radios --vendor=Baofeng
    mychirp-fw --diff antigo.bin novo.bin
"""

import argparse
import logging
import sys

import serial.tools.list_ports

from mychirp import logger  # noqa: F401  (configura logging/versão)

LOG = logging.getLogger(__name__)


def list_radios(vendor=None):
    """Lista identificações de drivers registrados (filtro por vendor)."""
    from mychirp import directory
    directory.import_drivers()
    ids = []
    for ident, rclass in sorted(directory.DRV_TO_RADIO.items()):
        if vendor and rclass.VENDOR.lower() != vendor.lower():
            continue
        ids.append(ident)
    print("Drivers%s: %d" % (" (vendor=%s)" % vendor if vendor else "",
                             len(ids)))
    for ident in ids:
        print("\t", ident)


def main(args=None):
    parser = argparse.ArgumentParser(
        description="mychirp-fw: dump de memória de rádio (read-only)")
    parser.add_argument("-s", "--serial", dest="serial",
                        default=None,
                        help="Porta serial (ex.: /dev/ttyUSB0, COM3)")
    parser.add_argument("-r", "--radio", dest="radio",
                        default=None,
                        help="Driver do rádio (ident do directory, "
                             "veja --list-radios)")
    parser.add_argument("--list-radios", action="store_true",
                        help="Listar drivers registrados")
    parser.add_argument("--vendor", dest="vendor",
                        default=None,
                        help="Filtro de fabricante p/ --list-radios")
    parser.add_argument("--out", dest="out", default=None,
                        help="Arquivo de saída (.bin); default: auto pelo "
                             "sha256")
    parser.add_argument("--backup", action="store_true",
                        help="Salvar em ~/.chirp/fw-backups/ além do --out")
    parser.add_argument("--diff", nargs=2, metavar=("A", "B"),
                        help="Comparar dois dumps byte a byte")
    logger.add_arguments(parser)
    parser.add_argument("args", metavar="arg", nargs='*',
                        help="Argumentos extras")
    options = parser.parse_args(args)
    logger.handle_options(options)

    from mychirp import fwtool

    if options.list_radios:
        list_radios(options.vendor)
        return 0

    if options.diff:
        a_path, b_path = options.diff
        a, b, ranges = fwtool.diff_files(a_path, b_path)
        print("Diff %s vs %s:" % (a_path, b_path))
        print(fwtool.format_diff(ranges, len(a), len(b)))
        return 0 if not ranges else 1

    from mychirp.serial_pipe import PortBusyError
    try:
        dump = fwtool.dump_clone(
            options.radio, options.serial,
            out=options.out, backup=options.backup)
    except fwtool.FwDumpError as e:
        LOG.error("%s", str(e))
        return 1
    except PortBusyError as e:
        LOG.error("Porta ocupada: %s", str(e))
        LOG.info("Feche o programa que está usando a porta e tente "
                 "de novo.")
        return 2
    return 0
