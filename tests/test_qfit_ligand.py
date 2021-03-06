import pytest
import os
import multiprocessing as mp

from qfit.qfit_ligand import (
    QFitLigandOptions,
    prepare_qfit_ligand,
    build_argparser,
    print_run_info
)


def setup_module(module):
    # Here, we add compatibility for multiprocessing coverage reports.
    # via: https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html#if-you-use-multiprocessing-pool
    try:
        from pytest_cov.embed import cleanup_on_sigterm
    except ImportError:
        pass
    else:
        cleanup_on_sigterm()


class TestQFitLigand:
    def mock_main(self):
        # Prepare args
        args = [
            "../example/composite_omit_map.mtz",  # mapfile, using relative directory from tests/
            "../example/4ms6.pdb",  # structurefile, using relative directory from tests/
            "-l", "2FOFCWT,PH2FOFCWT",
            "A, 702", #selection
            "--directory", f"{os.environ['QFIT_OUTPUT_DIR']}",
        ]

        # TODO: Add options to reduce computational load

        # Collect and act on arguments
        p = build_argparser()
        args = p.parse_args(args=args)
        try:
            os.mkdir(args.directory)
        except OSError:
            pass

        print_run_info(args)
        options = QFitLigandOptions()
        options.apply_command_args(args)

        # Build a QFitLigand job
        qfit_ligand = prepare_qfit_ligand(options)

        assert qfit_ligand.ligand.natoms == 19

        return qfit_ligand

    def test_run_qfit_ligand(self):
        qfit_ligand = self.mock_main()

        # Run qfit object
        # NOTE: Currently, running this qfit_ligand job takes 20-something
        #       minutes on the GitHub Actions runner. This needs to be cut down.

        # output = qfit_ligand.run() # TODO: Determine if you can just run part of this 
        # conformers = qfit_ligand.get_conformers()
        # assert len(conformers) == 3  # TODO: fix when qfit_ligand working
