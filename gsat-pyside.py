#!/usr/bin/env python
"""----------------------------------------------------------------------------
    gsat-pyside.py

    Entry point for the gsat PySide6 workbench (spike / successor desktop UI).

    Classic production UI remains gsat.py (wx). This client reuses the same
    backend (machif, progexec, gsat-server, remotes) as a thin shell.

    Dependencies (see requirements-pyside.txt):
        python3 -m venv .venv
        .venv/bin/pip install -r requirements-pyside.txt
        .venv/bin/python gsat-pyside.py
----------------------------------------------------------------------------"""
import os
import sys
import argparse

import modules.config as gc
import modules.version_info as vinfo
import modules.pyside_workbench as pyside_workbench


def get_cli_params():
    parser = argparse.ArgumentParser(
        description=f"{vinfo.__description__} (PySide workbench)"
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"{sys.argv[0]} {vinfo.__revision__} ({vinfo.__appname__} PySide)",
    )

    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        help="Use alternate configuration file name",
        metavar="FILE",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="print extra information to stdout",
    )

    parser.add_argument(
        "--vv",
        "--vverbose",
        dest="vverbose",
        action="store_true",
        default=False,
        help="print extra++ information to stdout",
    )

    mask_str = str(sorted(gc.VERBOSE_MASK_DICT.keys()))
    parser.add_argument(
        "--vm",
        "--verbose_mask",
        dest="verbose_mask",
        default=None,
        help=(
            "select verbose mask(s) separated by ','; the options are {}".format(
                mask_str
            )
        ),
        metavar="MASK",
    )

    options = parser.parse_args()

    if options.verbose_mask is not None:
        options.verbose_mask = gc.decode_verbose_mask_string(options.verbose_mask)
    elif options.verbose:
        options.verbose_mask = gc.VERBOSE_MASK_SERIALIF_STR
    elif options.vverbose:
        options.verbose_mask = gc.VERBOSE_MASK_SERIALIF_HEX
    else:
        options.verbose_mask = 0

    if options.vverbose:
        options.verbose = True

    # Attribute used by some shared modules (wx server mode); unused here
    if not hasattr(options, "server"):
        options.server = False

    if sys.version_info < (3, 8, 0):
        parser.error("** Required Python 3.8.2 or greater.")
        sys.exit(1)

    return options


if __name__ == "__main__":
    import faulthandler

    faulthandler.enable()

    cmd_line_options = get_cli_params()

    config_fname = cmd_line_options.config
    if config_fname is None:
        config_fname = os.path.abspath(os.path.expanduser("~/.gsat.json"))

    gc.init_config(cmd_line_options, config_fname, "log_file_pyside")

    raise SystemExit(pyside_workbench.run_app(cmd_line_options))
