"""
Quantum Prisoner's Dilemma - Qiskit Implementation
====================================================
Adapted from: "Bridging Theory and Practice in Quantum Game Theory:
Optimized Implementation of the Battle of the Sexes with Error
Mitigation on NISQ Hardware"  (Díaz Agreda et al., IEEE Chilecon)

Quantum PD formulation based on:
  Eisert, Wilkens & Lewenstein (1999) — "Quantum Games and Quantum Strategies"
  Physical Review Letters 83(15), 3077–3080.

This is the project's *extension* beyond the original paper (which only covered
Battle of the Sexes): the same simulation + GCM + validation pipeline applied to
the EWL Prisoner's Dilemma.

Game setup (standard PD payoff matrix):
  Both cooperate  (CC) → each gets R = 3  (Reward)
  Both defect     (DD) → each gets P = 1  (Punishment)
  One defects     (CD) → defector gets T = 5, cooperator gets S = 0  (Sucker)

Classical dominant strategy: always defect → (D,D) Nash equilibrium → payoff 1
Quantum "miracle move" Q: both players can reach (C,C) → payoff 3

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
GAMMA_VALUES = np.linspace(0, np.pi / 2, 31)   # γ ∈ [0, π/2]; π/2 = max entanglement

# Prisoner's Dilemma strategies (Eisert et al. 1999):
#   C = Cooperate → I ;  D = Defect → Ry(π) ;  H = Hadamard ;  Q = "miracle move" → Rz(π)
STRATEGIES = ["C", "D", "H", "Q"]

# Payoff vectors for outcomes ordered as |CC⟩, |CD⟩, |DC⟩, |DD⟩ (index = alice*2 + bob)
PAYOFF_A = np.array([3.0, 0.0, 5.0, 1.0])   # Alice's payoffs
PAYOFF_B = np.array([3.0, 5.0, 0.0, 1.0])   # Bob's payoffs (symmetric game)

# PD standard constants
R, T, P, S = 3, 5, 1, 0   # Reward, Temptation, Punishment, Sucker

FIG_NAMES = {"C": "fig_gcm_C", "D": "fig_gcm_D", "H": "fig_gcm_H", "Q": "fig_gcm_Q"}


# ══════════════════════════════════════════════════════════════════════════════
# §1 · CLASSICAL PRISONER'S DILEMMA
# ══════════════════════════════════════════════════════════════════════════════

def classical_dominant_strategy():
    """Defect strictly dominates (T>R, P>S); (D,D) Nash equilibrium pays P=1."""
    ea_ne = P
    print("=" * 60)
    print("CLASSICAL PRISONER'S DILEMMA")
    print("=" * 60)
    print(f"  Payoff matrix     : R={R}, T={T}, P={P}, S={S}")
    print(f"  Dominant strategy : Defect (D)")
    print(f"  Nash equilibrium  : (D, D)  →  payoff = {ea_ne} each")
    print(f"  Social optimum    : (C, C)  →  payoff = {R} each")
    print(f"  Efficiency loss   : {(R - ea_ne) / R:.0%} below social optimum\n")
    return 0.0, ea_ne


# ══════════════════════════════════════════════════════════════════════════════
# §2 · QISKIT CIRCUIT BUILDER  (EWL protocol with J and J†)
# ══════════════════════════════════════════════════════════════════════════════

def build_circuit(gamma: float, strategy: str) -> QuantumCircuit:
    """
    Construct the Eisert-Wilkens-Lewenstein (EWL) quantum PD circuit.

    EWL protocol: J(γ) entangle → local strategy gates → J†(γ) disentangle → measure.
      C (Cooperate) → I ; D (Defect) → Ry(π) ; H → Hadamard ; Q (miracle) → Rz(π).
    γ=0 recovers the classical game; γ=π/2 is maximum entanglement.
    """
    qc = QuantumCircuit(2, 2)

    # J(γ): entangle
    qc.ry(gamma, 0)
    qc.cx(0, 1)

    def apply_strategy(qubit: int, strat: str):
        if strat == "C":
            pass
        elif strat == "D":
            qc.ry(np.pi, qubit)
        elif strat == "H":
            qc.h(qubit)
        elif strat == "Q":
            qc.rz(np.pi, qubit)
        else:
            raise ValueError(f"Unknown strategy: {strat}")

    apply_strategy(0, strategy)  # Alice
    apply_strategy(1, strategy)  # Bob

    # J†(γ): disentangle
    qc.cx(0, 1)
    qc.ry(-gamma, 0)

    qc.measure([0, 1], [0, 1])
    return qc


def quantum_equilibrium(analytical: dict, classical_ne: float = 1.0):
    """Report the (Q,Q) payoff at maximum entanglement (γ=π/2 ≈ R)."""
    EA_Q, EB_Q = analytical["Q"]
    q_eq = float((EA_Q[-1] + EB_Q[-1]) / 2)
    improvement = (q_eq - classical_ne) / classical_ne * 100
    print(f"Quantum equilibrium payoff (Q strategy, γ=π/2) ≈ {q_eq:.2f}  →  "
          f"{improvement:.0f}% improvement over classical NE payoff {classical_ne}\n")
    return q_eq, improvement


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 60)
    print("  QUANTUM PRISONER'S DILEMMA – Qiskit Implementation")
    print("  (EWL protocol; extension of Díaz Agreda et al.)")
    print("=" * 60 + "\n")

    # §1 Classical baseline
    classical_dominant_strategy()

    # §2 Ideal payoffs via statevector simulation
    print("Computing ideal payoff curves (Qiskit statevector) …")
    analytical = analytical_payoffs_sv(GAMMA_VALUES, STRATEGIES, build_circuit, PAYOFF_A, PAYOFF_B)
    quantum_equilibrium(analytical, classical_ne=float(P))

    # §3 Without-GCM baseline
    print("Running without-GCM baseline …")
    base_all = baseline_noisy(GAMMA_VALUES, STRATEGIES, build_circuit, PAYOFF_A, PAYOFF_B)

    # §4 GCM runs
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

    print_rmse_table(gcm_summary, STRATEGIES, title="PD RMSE per strategy (with GCM)")
    print_comparison_table(comparison, STRATEGIES, title="PD — GCM vs no-GCM (paired t-test across γ)")

    print("\n" + "=" * 60)
    print("INTERPRETATION")
    print("=" * 60)
    print(f"  Classical NE (D,D)   → payoff = {P}  [Pareto-inferior]")
    print(f"  Social optimum (C,C) → payoff = {R}  [unstable classically]")
    print(f"  Quantum strategy Q   → payoff ≈ {R} at γ=π/2  [escapes the dilemma]")

    # §6 Figures (regenerated from code into PD/graphs/)
    print("\nSaving figures to PD/graphs/ …")
    save_payoff_curves(analytical, os.path.join(GRAPHS, "fig_analytical.png"),
                       gamma=GAMMA_VALUES, title="PD analytical payoffs")
    save_no_gcm_overview(base_summary, analytical, STRATEGIES, GAMMA_VALUES,
                         os.path.join(GRAPHS, "fig4_no_gcm.png"),
                         title="PD without GCM — experimental vs analytical")
    for s in STRATEGIES:
        save_payoff_with_ci(GAMMA_VALUES, gcm_summary[s]["EA_exp"], gcm_summary[s]["EB_exp"],
                            gcm_summary[s]["ci_ea"], gcm_summary[s]["ci_eb"],
                            analytical[s][0], analytical[s][1],
                            os.path.join(GRAPHS, FIG_NAMES[s] + ".png"),
                            title=f"PD with GCM — Strategy {s}")
    save_multiple_runs(gcm_all["Q"], analytical["Q"][0], analytical["Q"][1], GAMMA_VALUES,
                       os.path.join(GRAPHS, "fig9_multiple_runs.png"),
                       title=f"PD — {N_REPETITIONS} runs (Strategy Q) with GCM")
    save_rmse_bar(gcm_summary, os.path.join(GRAPHS, "fig_rmse_bar.png"),
                  title="PD RMSE per strategy (with GCM)")
    save_rmse_comparison(comparison, STRATEGIES, os.path.join(GRAPHS, "fig_rmse_comparison.png"),
                         title="PD RMSE: without GCM vs with GCM")

    print("Done.")
    return dict(analytical=analytical, base_summary=base_summary,
                gcm_summary=gcm_summary, comparison=comparison)


if __name__ == "__main__":
    main()
