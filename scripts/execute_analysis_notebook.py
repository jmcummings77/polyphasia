"""Execute the verified analysis notebook in a fresh, temporary Python kernel.

The kernel uses this command's interpreter, so no global Jupyter kernel needs
to be installed. The source notebook and existing outputs are never replaced.
Install the notebook extra before running this script.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import nbformat
from jupyter_client import AsyncKernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient


def execute_notebook(
    notebook: Path, artifacts: Path, output: Path, *, timeout: int = 120
) -> None:
    """Read verified artifacts in a fresh kernel and save a new executed copy.

    ``timeout`` limits each cell. Exceptions, including cells tagged as expected
    failures, abort execution without writing an apparently successful output.
    """
    notebook, artifacts, output = (
        Path(path).resolve() for path in (notebook, artifacts, output)
    )
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if not artifacts.is_dir():
        raise NotADirectoryError(f"Artifact directory does not exist: {artifacts}")

    document = nbformat.read(notebook, as_version=4)
    nbformat.validate(document)
    for cell in document.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None
    document.metadata.pop("widgets", None)

    with tempfile.TemporaryDirectory(prefix="polyphasia-kernel-") as temporary:
        kernel_root = Path(temporary)
        kernel_name = "polyphasia-analysis"
        kernel_directory = kernel_root / kernel_name
        kernel_directory.mkdir()
        specification = {
            "argv": [
                sys.executable,
                "-m",
                "ipykernel_launcher",
                "-f",
                "{connection_file}",
            ],
            "display_name": "Polyphasia analysis (current interpreter)",
            "language": "python",
        }
        (kernel_directory / "kernel.json").write_text(
            json.dumps(specification), encoding="utf-8"
        )
        manager = AsyncKernelManager(
            kernel_name=kernel_name,
            kernel_spec_manager=KernelSpecManager(kernel_dirs=[str(kernel_root)]),
            connection_file=str(kernel_root / "connection.json"),
        )
        client = NotebookClient(
            document,
            km=manager,
            kernel_name=kernel_name,
            timeout=timeout,
            allow_errors=False,
            force_raise_errors=True,
            record_timing=False,
        )
        environment = os.environ.copy()
        environment["POLYPHASIA_ANALYSIS_DIR"] = str(artifacts)
        environment["IPYTHONDIR"] = str(kernel_root / "ipython")
        client.execute(cwd=str(notebook.parent), env=environment, cleanup_kc=True)

    nbformat.validate(document)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        nbformat.write(document, stream)


def main() -> None:
    """Parse explicit artifact/output paths and execute the notebook."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notebook",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "notebooks"
        / "verified_analysis.ipynb",
        help="Source notebook (default: notebooks/verified_analysis.ipynb)",
    )
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=120, help="Seconds per cell")
    arguments = parser.parse_args()
    execute_notebook(
        arguments.notebook,
        arguments.artifacts,
        arguments.output,
        timeout=arguments.timeout,
    )
    print(f"Executed notebook saved to {arguments.output.resolve()}")


if __name__ == "__main__":
    main()
