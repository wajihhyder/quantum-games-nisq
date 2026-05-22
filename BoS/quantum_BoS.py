"""
Quantum Battle of the Sexes - Qiskit Implementation
=====================================================
Based on: "Bridging Theory and Practice in Quantum Game Theory:
Optimized Implementation of the Battle of the Sexes with Error
Mitigation on NISQ Hardware"  (Díaz Agreda et al., IEEE Chilecon)

This is a *simulation* replication (qiskit-aer noise model, not real hardware)
that additionally demonstrates the GCM improvement with a with-vs-without-GCM
comparison and the paired t-test the original paper deferred to future work.

Dependencies: qiskit>=2.0, qiskit-aer>=0.13, numpy, scipy, matplotlib
"""

import os
import sys
import pathlib
import numpy as np

from qiskit import QuantumCircuit

# Windows consoles default to cp1252, which cannot encode γ/π/→; emit UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is importable when running this script directly
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from quantum_common import (
    N_SHOTS, N_REPETITIONS,
    analytical_payoffs_sv, baseline_noisy, GCMStrategy, validate,
    compare_gcm_vs_baseline, print_rmse_table, print_comparison_table,
)
from graph_helpers import (
    save_payoff_curves, save_rmse_bar, save_rmse_comparison,
    save_payoff_with_ci, save_no_gcm_overview, save_multiple_runs,
)

GRAPHS = str(pathlib.Path(__file__).resolve().parent / "graphs")

# ─── Hyper-parameters ─────────────────────────────────────────────────────────
GAMMA_VALUES = np.linspace(0, np.pi, 31)
STRATEGIES   = ["I", "H", "R_pi4", "R_pi"]
PAYOFF_A     = np.array([3, 0, 0, 2], dtype=float)   # |00⟩,|01⟩,|10⟩,|11⟩
PAYOFF_B     = np.array([2, 0, 0, 3], dtype=float)

# Filenames preserved from the original BoS/graphs/ set.
FIG_NAMES = {"I": "fig_gcm_I", "H": "fig_gcm_H", "R_pi4": "fig_gcm_R_pi4", "R_pi": "fig_gcm_R_pi"}


# ══════════════════════════════════════════════════════════════════════════════
# §1 · CLASSICAL BATTLE OF THE SEXES
# ══════════════════════════════════════════════════════════════════════════════

def classical_mixed_equilibrium():
    P, Q = 3 / 5, 2 / 5
    EA = 3 * P * Q + 2 * (1 - P) * (1 - Q)
    EB = 2 * P * Q + 3 * (1 - P) * (1 - Q)
    mis = P * (1 - Q) + (1 - P) * Q
    print("=" * 60)
    print("CLASSICAL BATTLE OF THE SEXES – Mixed Nash Equilibrium")
    print("=" * 60)
    print(f"  Alice plays Opera : P = {P:.4f}")
    print(f"  Bob   plays Opera : Q = {Q:.4f}")
    print(f"  Expected payoff   : EA = EB = {EA:.4f}")
    print(f"  Miscoordination   : {mis:.2%}\n")
    return P, Q, EA, EB


# ══════════════════════════════════════════════════════════════════════════════
# §2 · QISKIT CIRCUIT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_circuit(gamma: float, strategy: str) -> QuantumCircuit:
    """
    Construct the BoS quantum circuit (Fig. 1).

    Qubit layout:
      q[0] = Alice (Qiskit little-endian → bit 1)
      q[1] = Bob   (→ bit 0)

    Steps:
      1. Ry(γ) on Alice
      2. CNOT(Alice → Bob)  – entanglement
      3. Strategy gates on both qubits
      4. Measure both qubits
    """
    qc = QuantumCircuit(2, 2)

    qc.ry(gamma, 0)        # Alice
    qc.cx(0, 1)            # CNOT: control=Alice, target=Bob

    if strategy == "I":
        pass
    elif strategy == "H":
        qc.h(0); qc.h(1)
    elif strategy == "R_pi4":
        qc.ry(np.pi / 4, 0); qc.ry(np.pi / 4, 1)
    elif strategy == "R_pi":
        qc.ry(np.pi, 0); qc.ry(np.pi, 1)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    qc.measure([0, 1], [0, 1])
    return qc


def quantum_equilibrium(analytical: dict, classical_payoff: float = 1.2):
    """Derive the (EA=EB) crossing payoff from the simulated curves (≈ 2.5)."""
    EA, EB = analytical["I"]
    idx = int(np.argmin(np.abs(EA - EB)))
    q_eq = float((EA[idx] + EB[idx]) / 2)
    improvement = (q_eq - classical_payoff) / classical_payoff * 100
    print(f"Quantum equilibrium payoff = {q_eq:.2f} (at γ = {GAMMA_VALUES[idx]:.2f})  →  "
          f"{improvement:.0f}% improvement over classical {classical_payoff}\n")
    return q_eq, improvement


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 60)
    print("  QUANTUM BATTLE OF THE SEXES – Qiskit Implementation")
    print("  (Díaz Agreda et al., IEEE Chilecon) — simulation replication")
    print("=" * 60 + "\n")

    # §1 Classical baseline
    classical_mixed_equilibrium()

    # §2 Ideal payoffs via Qiskit statevector simulator
    print("Computing ideal payoff curves (Qiskit statevector) …")
    analytical = analytical_payoffs_sv(GAMMA_VALUES, STRATEGIES, build_circuit, PAYOFF_A, PAYOFF_B)
    quantum_equilibrium(analytical, classical_payoff=1.2)

    # §3 Without-GCM baseline (single noisy backend, dense packing → crosstalk)
    print("Running without-GCM baseline …")
    base_all = baseline_noisy(GAMMA_VALUES, STRATEGIES, build_circuit, PAYOFF_A, PAYOFF_B)

    # §4 GCM runs (adaptive low-error routing, no crosstalk)
    print("Running with GCM strategy …")
    gcm = GCMStrategy(n_slots=len(GAMMA_VALUES))
    gcm_all = {}
    for s in STRATEGIES:
        print(f"  Strategy {s} …", flush=True)
        gcm_all[s] = gcm.run(GAMMA_VALUES, s, build_circuit, PAYOFF_A, PAYOFF_B, N_SHOTS, N_REPETITIONS)

    # §5 Validation + improvement quantification
    base_summary = validate(base_all, analytical, STRATEGIES)
    gcm_summary = validate(gcm_all, analytical, STRATEGIES)
    comparison = compare_gcm_vs_baseline(gcm_summary, base_summary, analytical, STRATEGIES)

    print_rmse_table(gcm_summary, STRATEGIES, title="BoS RMSE per strategy (with GCM) — cf. Table II")
    print_comparison_table(comparison, STRATEGIES, title="BoS — GCM vs no-GCM (paired t-test across γ)")

    # §6 Figures (regenerated from code into BoS/graphs/)
    print("\nSaving figures to BoS/graphs/ …")
    save_payoff_curves(analytical, os.path.join(GRAPHS, "fig_analytical.png"),
                       gamma=GAMMA_VALUES, title="BoS analytical payoffs")
    save_no_gcm_overview(base_summary, analytical, STRATEGIES, GAMMA_VALUES,
                         os.path.join(GRAPHS, "fig4_no_gcm.png"),
                         title="BoS without GCM — experimental vs analytical")
    for s in STRATEGIES:
        save_payoff_with_ci(GAMMA_VALUES, gcm_summary[s]["EA_exp"], gcm_summary[s]["EB_exp"],
                            gcm_summary[s]["ci_ea"], gcm_summary[s]["ci_eb"],
                            analytical[s][0], analytical[s][1],
                            os.path.join(GRAPHS, FIG_NAMES[s] + ".png"),
                            title=f"BoS with GCM — Strategy {s}")
    save_multiple_runs(gcm_all["I"], analytical["I"][0], analytical["I"][1], GAMMA_VALUES,
                       os.path.join(GRAPHS, "fig9_multiple_runs.png"),
                       title=f"BoS — {N_REPETITIONS} runs (Strategy I) with GCM")
    save_rmse_bar(gcm_summary, os.path.join(GRAPHS, "fig_rmse_bar.png"),
                  title="BoS RMSE per strategy (with GCM)")
    save_rmse_comparison(comparison, STRATEGIES, os.path.join(GRAPHS, "fig_rmse_comparison.png"),
                         title="BoS RMSE: without GCM vs with GCM")

    print("Done.")
    return dict(analytical=analytical, base_summary=base_summary,
                gcm_summary=gcm_summary, comparison=comparison)


if __name__ == "__main__":
    main()
