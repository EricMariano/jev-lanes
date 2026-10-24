"""Execute the five-minute notebook without external providers.

    uv run --group notebook python examples/execute_notebook.py

The executed copy is written to ignored ``build/``, keeping the source notebook clean.
"""

import os
import sys
from pathlib import Path

import nbformat
from jupyter_client import KernelManager
from nbclient import NotebookClient


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    notebook = nbformat.read(root / "examples" / "quickstart.ipynb", as_version=4)
    nbformat.validate(notebook)
    # Use this interpreter's kernel, even when the user's default kernel is elsewhere.
    manager = KernelManager(kernel_name="python3", transport="ipc" if os.name == "posix" else "tcp")
    manager.kernel_spec.argv = [
        sys.executable,
        "-m",
        "ipykernel_launcher",
        "-f",
        "{connection_file}",
    ]
    client = NotebookClient(
        notebook, km=manager, timeout=60, resources={"metadata": {"path": str(root)}}
    )
    try:
        client.execute()
    finally:
        if manager.has_kernel:
            manager.shutdown_kernel(now=True)
    output = root / "build" / "quickstart.executed.ipynb"
    output.parent.mkdir(exist_ok=True)
    nbformat.write(notebook, output)
    print(f"Notebook executed successfully: {output}")


if __name__ == "__main__":
    main()
