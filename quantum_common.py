"""
Shared utilities for quantum game simulations.

This module centralises common imports, noise model/backends,
simulation helpers and GCM logic used by both BoS and PD runners.

Replication note
----------------
The original paper (Diaz Agreda et al., IEEE Chilecon) ran on the real
``ibm_sherbrooke`` superconducting processor. This project reproduces that
workflow *in simulation* using qiskit-aer with a calibrated NISQ noise model.
The two execution conditions compared throughout are:

* **without GCM** -- a single noisy backend in which the 31 circuits are run
  "simultaneously"; dense packing induces extra two-qubit crosstalk
  (modelled by ``CROSSTALK_NO_GCM``), reproducing the chaotic curves of Fig. 4.
* **with GCM** -- the Guided Circuit Mapping strategy adaptively routes each
  circuit to a low-error, well-separated qubit pair, so the effective gate
  error is lower and crosstalk is negligible.
"""
import warnings
import numpy as np
from scipy import stats

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    ReadoutError,
    depolarizing_error,
    amplitude_damping_error,
)

warnings.filterwarnings("ignore")

# Shared constants
N_SHOTS = 2048
# Paper used 5 repetitions and flagged "scale to >=20 for a paired t-test" as
# future work. In simulation repetitions are cheap, so we honour that here.
N_REPETITIONS = 20
RNG = np.random.default_rng(42)

# Extra two-qubit depolarising error representing uncontrolled crosstalk when
# all circuits are packed onto the device at once (the "without GCM" condition).
CROSSTALK_NO_GCM = 0.02

# Shared statevector backend
_SV_BACKEND = AerSimulator(method="statevector")


def build_noise_model(p1=1e-3, p2=2.5e-3, ro=0.01, t1_frac=2e-4, crosstalk=0.0) -> NoiseModel:
    nm = NoiseModel()
    nm.add_all_qubit_quantum_error(depolarizing_error(p2 + crosstalk, 2), ["cx"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), ["ry", "h", "rz"])
    ad = amplitude_damping_error(t1_frac)
    nm.add_all_qubit_quantum_error(ad, ["measure"])
    ro_matrix = [[1 - ro, ro], [ro, 1 - ro]]
    nm.add_all_qubit_readout_error(ReadoutError(ro_matrix))
    return nm


def build_noisy_backend(scale=1.0, crosstalk=0.0) -> AerSimulator:
    nm = build_noise_model(
        p1=1e-3 * scale,
        p2=2.5e-3 * scale,
        ro=0.01 * scale,
        t1_frac=2e-4 * scale,
        crosstalk=crosstalk,
    )
    return AerSimulator(noise_model=nm)


def _counts_to_probs(counts: dict) -> np.ndarray:
    """Map raw bitstring counts to a length-4 probability vector.

    Index = alice * 2 + bob, matching the |00>,|01>,|10>,|11> payoff ordering.
    Qiskit returns bitstrings as c1 c0, so bitstr[0]=Bob (q1), bitstr[1]=Alice (q0).
    """
    probs = np.zeros(4)
    for bitstr, cnt in counts.items():
        bob = int(bitstr[0])
        alice = int(bitstr[1])
        probs[alice * 2 + bob] += cnt
    probs /= probs.sum()
    return probs


def simulate_ideal_probs(gamma: float, strategy: str, build_circuit, sv_backend=_SV_BACKEND, n_shots=N_SHOTS) -> np.ndarray:
    qc = build_circuit(gamma, strategy)
    t = transpile(qc, sv_backend)
    counts = sv_backend.run(t, shots=n_shots).result().get_counts()
    return _counts_to_probs(counts)


def analytical_payoffs_sv(gamma_array, strategies, build_circuit, payoff_A, payoff_B):
    result = {}
    for s in strategies:
        EA_list, EB_list = [], []
        for g in gamma_array:
            probs = simulate_ideal_probs(g, s, build_circuit)
            EA_list.append(payoff_A @ probs)
            EB_list.append(payoff_B @ probs)
        result[s] = (np.array(EA_list), np.array(EB_list))
    return result


def run_noisy(gamma: float, strategy: str, build_circuit, payoff_A, payoff_B, backend: AerSimulator, n_shots: int = N_SHOTS) -> tuple[float, float]:
    qc = build_circuit(gamma, strategy)
    t = transpile(qc, backend)
    counts = backend.run(t, shots=n_shots).result().get_counts()
    probs = _counts_to_probs(counts)
    return float(payoff_A @ probs), float(payoff_B @ probs)


def run_noisy_reps(gamma: float, strategy: str, build_circuit, payoff_A, payoff_B,
                   backend: AerSimulator, n_reps: int = N_REPETITIONS, n_shots: int = N_SHOTS):
    """Run ``n_reps`` independent noisy executions. Transpiles once, returns (EA[], EB[])."""
    qc = build_circuit(gamma, strategy)
    t = transpile(qc, backend)
    ea_list, eb_list = [], []
    for _ in range(n_reps):
        counts = backend.run(t, shots=n_shots).result().get_counts()
        probs = _counts_to_probs(counts)
        ea_list.append(float(payoff_A @ probs))
        eb_list.append(float(payoff_B @ probs))
    return np.array(ea_list), np.array(eb_list)


def _pack_reps(ea_r: np.ndarray, eb_r: np.ndarray) -> dict:
    return {
        "mean_EA": ea_r.mean(), "mean_EB": eb_r.mean(),
        "std_EA":  ea_r.std(),  "std_EB":  eb_r.std(),
        "all_EA":  ea_r,        "all_EB":  eb_r,
    }


def baseline_noisy(gamma_array, strategies, build_circuit, payoff_A, payoff_B,
                   scale: float = 1.0, crosstalk: float = CROSSTALK_NO_GCM,
                   n_reps: int = N_REPETITIONS, n_shots: int = N_SHOTS) -> dict:
    """Without-GCM baseline: one noisy backend, dense packing -> extra crosstalk.

    Produces the same per-gamma structure as :meth:`GCMStrategy.run` so the
    validation/comparison helpers work uniformly on both conditions.
    """
    backend = build_noisy_backend(scale=scale, crosstalk=crosstalk)
    out = {}
    for s in strategies:
        res = []
        for gamma in gamma_array:
            ea_r, eb_r = run_noisy_reps(gamma, s, build_circuit, payoff_A, payoff_B,
                                        backend, n_reps, n_shots)
            res.append(_pack_reps(ea_r, eb_r))
        out[s] = res
    return out


class GCMStrategy:
    """Generalised GCM strategy that can operate with a game-specific build_circuit.

    Models the paper's Guided Circuit Mapping: 31 low-error, well-separated qubit
    pairs ("slots") are curated, each circuit is routed to the lowest-error slot,
    and slot error estimates are refined from observed run-to-run variability.
    Because the pairs are spaced apart, crosstalk is negligible (``crosstalk=0``),
    and the per-slot scale stays at or below the nominal device error.

    Use ``.run(gamma_array, strategy, build_circuit, payoff_A, payoff_B)`` to execute.
    """
    def __init__(self, n_slots: int = 31, crosstalk: float = 0.0):
        self.n_slots = n_slots
        self.crosstalk = crosstalk
        self.slot_err = RNG.uniform(0.005, 0.025, n_slots)

    def _sorted_slots(self):
        return list(np.argsort(self.slot_err))

    def _update(self, slot: int, rmse: float, alpha: float = 0.3):
        self.slot_err[slot] = (1 - alpha) * self.slot_err[slot] + alpha * rmse

    def _scale_for(self, slot: int) -> float:
        # slot_err in [0.005, 0.025] -> scale in [0.6, 1.0]: curated pairs are
        # at or below the nominal (scale=1.0) device error.
        return 0.5 + self.slot_err[slot] / 0.05

    def run(self, gamma_array, strategy: str, build_circuit, payoff_A, payoff_B,
            n_shots: int = N_SHOTS, n_reps: int = N_REPETITIONS):
        slots = self._sorted_slots()
        results = []

        for idx, gamma in enumerate(gamma_array):
            slot = slots[idx % self.n_slots]
            backend = build_noisy_backend(scale=self._scale_for(slot), crosstalk=self.crosstalk)

            ea_r, eb_r = run_noisy_reps(gamma, strategy, build_circuit, payoff_A, payoff_B,
                                        backend, n_reps, n_shots)
            self._update(slot, float(ea_r.std()))
            results.append(_pack_reps(ea_r, eb_r))

        return results


def rmse(exp: np.ndarray, ana: np.ndarray) -> float:
    return float(np.sqrt(np.mean((exp - ana) ** 2)))


def validate(all_results: dict, analytical: dict, strategies, n_reps: int = N_REPETITIONS) -> dict:
    """Compute RMSE (vs analytical) and 95% Student-t CIs for each strategy."""
    summary = {}
    for s in strategies:
        res = all_results[s]
        EA_exp = np.array([r["mean_EA"] for r in res])
        EB_exp = np.array([r["mean_EB"] for r in res])
        EA_ana, EB_ana = analytical[s]

        rmse_ea = rmse(EA_exp, EA_ana)
        rmse_eb = rmse(EB_exp, EB_ana)

        all_EA = np.vstack([r["all_EA"] for r in res])
        all_EB = np.vstack([r["all_EB"] for r in res])
        ci_ea = stats.t.interval(0.95, df=n_reps - 1,
                                 loc=all_EA.mean(1),
                                 scale=stats.sem(all_EA, 1) + 1e-10)
        ci_eb = stats.t.interval(0.95, df=n_reps - 1,
                                 loc=all_EB.mean(1),
                                 scale=stats.sem(all_EB, 1) + 1e-10)

        summary[s] = dict(rmse_ea=rmse_ea, rmse_eb=rmse_eb,
                           ci_ea=ci_ea,    ci_eb=ci_eb,
                           EA_exp=EA_exp,  EB_exp=EB_exp)

    return summary


def compare_gcm_vs_baseline(gcm_summary: dict, base_summary: dict, analytical: dict, strategies) -> dict:
    """Quantify the GCM improvement over the no-GCM baseline.

    For each strategy and player, computes the RMSE under both conditions, the
    relative RMSE reduction, and a paired t-test (paired across the gamma sweep
    on the per-point absolute error) testing whether GCM significantly reduces
    error. This is the rigorous paired-t test the paper deferred to future work.
    """
    rows = {}
    for s in strategies:
        EA_ana, EB_ana = analytical[s]

        base_abs_A = np.abs(base_summary[s]["EA_exp"] - EA_ana)
        gcm_abs_A  = np.abs(gcm_summary[s]["EA_exp"]  - EA_ana)
        base_abs_B = np.abs(base_summary[s]["EB_exp"] - EB_ana)
        gcm_abs_B  = np.abs(gcm_summary[s]["EB_exp"]  - EB_ana)

        t_ea = stats.ttest_rel(base_abs_A, gcm_abs_A)
        t_eb = stats.ttest_rel(base_abs_B, gcm_abs_B)

        base_ea, gcm_ea = base_summary[s]["rmse_ea"], gcm_summary[s]["rmse_ea"]
        base_eb, gcm_eb = base_summary[s]["rmse_eb"], gcm_summary[s]["rmse_eb"]

        def _reduction(b, g):
            return (b - g) / b * 100 if b > 0 else 0.0

        rows[s] = dict(
            base_rmse_ea=base_ea, gcm_rmse_ea=gcm_ea, red_ea=_reduction(base_ea, gcm_ea),
            base_rmse_eb=base_eb, gcm_rmse_eb=gcm_eb, red_eb=_reduction(base_eb, gcm_eb),
            t_ea=float(t_ea.statistic), p_ea=float(t_ea.pvalue),
            t_eb=float(t_eb.statistic), p_eb=float(t_eb.pvalue),
        )
    return rows


def print_rmse_table(summary: dict, strategies, title: str = "RMSE per strategy (with GCM)"):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    print(f"  {'Strategy':<10}{'EA RMSE':>12}{'EB RMSE':>12}")
    for s in strategies:
        print(f"  {s:<10}{summary[s]['rmse_ea']:>12.4f}{summary[s]['rmse_eb']:>12.4f}")


def print_comparison_table(rows: dict, strategies, title: str = "GCM vs no-GCM (paired t-test)"):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)
    print(f"  {'Strategy':<9}{'noGCM EA':>10}{'GCM EA':>9}{'red%':>7}{'p(EA)':>9}"
          f"{'noGCM EB':>11}{'GCM EB':>9}{'red%':>7}{'p(EB)':>9}")
    for s in strategies:
        r = rows[s]
        print(f"  {s:<9}{r['base_rmse_ea']:>10.4f}{r['gcm_rmse_ea']:>9.4f}"
              f"{r['red_ea']:>6.0f}%{r['p_ea']:>9.2e}"
              f"{r['base_rmse_eb']:>11.4f}{r['gcm_rmse_eb']:>9.4f}"
              f"{r['red_eb']:>6.0f}%{r['p_eb']:>9.2e}")
