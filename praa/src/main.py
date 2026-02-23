import sys
from pathlib import Path


def main() -> None:
    # Determine base directory (where config.json and assets/ live)
    # When running from source: d:\tts-edge\praa\src\main.py → base = d:\tts-edge\praa
    # When running from exe: the exe's directory
    if getattr(sys, "frozen", False):
        # Running as compiled exe (Nuitka/PyInstaller)
        base_dir = Path(sys.executable).parent
    else:
        # Running from source
        base_dir = Path(__file__).resolve().parent.parent

    # Fix encoding for Nuitka console output (prevents crash on non-ASCII logging)
    if getattr(sys, "frozen", False):
        import io

        if sys.stdout:
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
        if sys.stderr:
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace"
            )

    # Add src to path for imports
    src_dir = base_dir / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    from src.application.bootstrap import Application

    app = Application(base_dir)
    app.run()


if __name__ == "__main__":
    main()
