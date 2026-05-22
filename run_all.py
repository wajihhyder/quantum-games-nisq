"""
Single entry point: run both quantum game simulations end-to-end.

Regenerates every figure (into BoS/graphs/ and PD/graphs/) and prints the
RMSE tables and the with-vs-without-GCM paired t-test comparisons from scratch.

Usage:
    python run_all.py
"""
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SCRIPTS = [ROOT / "BoS" / "quantum_BoS.py", ROOT / "PD" / "quantum_PD.py"]


def main():
    for script in SCRIPTS:
        print("\n" + "#" * 70, flush=True)
        print(f"# Running {script.relative_to(ROOT)}", flush=True)
        print("#" * 70, flush=True)
        subprocess.run([sys.executable, str(script)], check=True)
    print("\nAll simulations complete. Figures written to BoS/graphs/ and PD/graphs/.", flush=True)


if __name__ == "__main__":
    main()
