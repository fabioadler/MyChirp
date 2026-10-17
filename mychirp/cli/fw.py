#!/usr/bin/env python3
"""mychirp-fw — dump/restore de memória de rádio via protocolo de clonagem do driver.

Usage:
    mychirp-fw --serial=/dev/ttyUSB0 --radio=BAOFENG_BF-777S
    mychirp-fw --serial=COM3 --radio=BAOFENG_UV-5R --backup
    mychirp-fw --serial=/dev/ttyUSB0 --radio=BOMVINK_BOM-5701 --full-window
    mychirp-fw --list-radios --vendor=Baofeng
    mychirp-fw --diff antigo.bin novo.bin
    mychirp-fw --map dump.bin
    mychirp-fw --radio=Baofeng_BF-777S --serial=/dev/ttyUSB0 --restore backup.bin
"""

import argparse
import logging
import sys

import serial.tools.list_ports

from mychirp import directory  # noqa: F401 (resolvido no _fw_restore)
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


def _fw_restore(radio_id, port, image_path, data_len):
    """Anúncio do que vai acontecer fisicamente, antes da 1ª confirmação."""
    from mychirp import fwtool
    rclass = fwtool.resolve_rclass(radio_id)
    print("O seguinte será enviado para o rádio em %s (%s):"
          % (port, directory.get_driver(rclass)))
    print("- entra em PROGRAM e LÊ a janela clone %d B (read-only)"
          % fwtool.H777_WINDOW_END)
    print("- ESCRITA em %d blocos de 8 B (janela clone %d B)"
          % (fwtool.H777_WINDOW_END // 8, fwtool.H777_WINDOW_END))
    print("- re-leitura completa pós-escrita para diff/verify")
    print("- imagem: %s (%d B)" % (image_path, data_len))
    print("- backups .pre/.post em ~/.chirp/fw-backups/")


def _fw_restore_confirm(radio_id, image_path):
    """Dupla confirmação via stdin: phase 1 explícita (sim/Não), phase 2
    exige digitar GRAVAR."""
    import os
    if not os.isatty(0):
        print("Sem TTY: confirmação humana IMPOSSÍVEL — escrita "
              "CANCELADA por segurança (use terminal interativo).")
        return False
    r1 = input("Confirma a ESCRITA no rádio? (sim/NÃO): ").strip().lower()
    if r1 not in ("sim", "s", "yes", "y"):
        return False
    r2 = input("Digite GRAVAR para confirmar definitivamente: ").strip()
    return r2 == "GRAVAR"


def main(args=None):
    parser = argparse.ArgumentParser(
        prog="mychirp-fw",
        description="mychirp-fw: dump e restauro de memória de rádio "
                    "(dump read-only; restore exige dupla confirmação)")
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
    parser.add_argument("--full-window", action="store_true",
                        help="Dump da janela completa cabelada (só drivers "
                             "com download_full_window, ex.: BOM-5701)")
    parser.add_argument("--diff", nargs=2, metavar=("A", "B"),
                        help="Comparar dois dumps byte a byte")
    parser.add_argument("--map", dest="map_dump", metavar="DUMP",
                        default=None,
                        help="Análise semântica de um dump (canais, "
                             "settings, regiões mapeadas vs não-mapeadas)")
    parser.add_argument("--restore", metavar="IMAGE",
                        default=None,
                        help="ESCREVE uma imagem de clone na janela do "
                             "rádio (operação de gravação; exige dupla "
                             "confirmação no terminal). Só família h777 "
                             "(992 B) validada — use APENAS o backup da "
                             "MESMA unidade (resgate)")
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
        from mychirp import fwtool as _fw
        a_path, b_path = options.diff
        a, b, ranges = _fw.diff_files(a_path, b_path)
        print("Diff %s vs %s:" % (a_path, b_path))
        print(_fw.format_diff(ranges, len(a), len(b)))
        return 0 if not ranges else 1

    if options.map_dump:
        from mychirp import fwtool as _fw
        try:
            rclass = None
            if options.radio:
                rclass = _fw.resolve_rclass(options.radio)
            an = _fw.analyze_dump(options.map_dump, rclass=rclass)
            print(_fw.format_map(an))
            return 0
        except _fw.FwDumpError as e:
            LOG.error("%s", str(e))
            return 1

    if options.restore:
        # Escrita (resgate) — exige dupla confirmação humana no terminal
        from mychirp import fwtool as _fw
        from mychirp.serial_pipe import PortBusyError as _PBE
        if not options.radio or not options.serial:
            LOG.error("--restore exige --radio e --serial")
            return 2
        image_path = options.args[0] if options.args else options.restore
        try:
            with open(image_path, "rb") as f:
                data_len = len(f.read())
        except OSError as e:
            LOG.error("Imagem inacessível: %s", e)
            return 2
        _fw_restore(options.radio, options.serial, image_path, data_len)
        if not _fw_restore_confirm(options.radio, image_path):
            print("Escrita cancelada pelo usuário.")
            return 3
        try:
            rep = _fw.restore_h777_image(
                options.radio, options.serial,
                open(image_path, "rb").read())
        except _fw.FwDumpError as e:
            LOG.error("%s", str(e))
            return 1
        except _PBE as e:
            LOG.error("Porta ocupada: %s", str(e))
            return 2
        ok = rep["ok"] and rep["diffs"] == []
        print("sha_antigo:", (rep["sha_old"] or "-")[:16])
        print("sha_novo:  ", (rep["sha_new"] or "-")[:16])
        print("pre:  %s" % rep["pre_path"])
        print("post: %s" % rep["post_path"])
        if rep["aborted"] is not None:
            print("Gravação ABORTADA em 0x%04X (NACK/timeout)."
                  % rep["aborted"])
            return 4
        if not ok:
            print("%d divergências pós-gravação (primeira: 0x%04X)"
                  % (len(rep["diffs"]), rep["diffs"][0]))
            return 5
        print("RESTORE OK: 0 divergências (re-leitura idêntica).")
        return 0

    from mychirp.serial_pipe import PortBusyError
    try:
        if options.full_window:
            dump = fwtool.dump_full_window(
                options.radio, options.serial,
                out=options.out, backup=options.backup)
        else:
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
