# quantum-games-nisq

A simulation of quantum game theory on Noisy Intermediate-Scale Quantum (NISQ) devices. This project takes two classic strategic decision-making games, the Battle of the Sexes and the Prisoner's Dilemma, runs them through a quantum computing framework, and shows that quantum strategies consistently outperform their classical counterparts, even in the presence of realistic hardware noise. It also includes a full IEEE conference paper.

The project replicates and extends the work of Díaz Agreda et al., *"Bridging Theory and Practice in Quantum Game Theory: Optimized Implementation of the Battle of the Sexes with Error Mitigation on NISQ Hardware"*, IEEE Chilecon 2023. Original code: [github.com/Carlosandp/GCMStrategy](https://github.com/Carlosandp/GCMStrategy)

---

## Game Theory

**Game theory** is the study of how rational people make decisions when what happens to each person depends on what everyone else does. Two of the most well-known examples are:

**The Prisoner's Dilemma.** Two suspects are interrogated separately. If both stay silent (cooperate), they each get a light sentence (a payoff of 3 each). If both confess, they both get a heavy sentence (a payoff of 1 each). If one confesses while the other stays silent, the one who confessed walks free (payoff 5) and the one who stayed silent gets the maximum penalty (payoff 0). Even though staying silent is the best joint outcome, each person's self-interest pushes them to confess. This leads to a **Nash equilibrium**, a situation where neither player can do better by changing only their own decision. The problem is that the Nash equilibrium here (both confess, payoff 1 each) is much worse than what they could have had by cooperating (payoff 3 each).

**The Battle of the Sexes.** Alice and Bob want to spend the evening together. Alice prefers the Opera and Bob prefers Football, but both would rather be in the same place than go alone. There is no obviously right answer: both possible outcomes where they attend together are Nash equilibria, but in the **mixed-strategy Nash equilibrium**, where each player randomises between the two choices, each player ends up with an expected payoff of only about 1.2, well below what they could get by coordinating perfectly.

---

## Quantum Game Theory

**Quantum game theory** takes these classical games and adds quantum mechanics. In the classical versions, each player picks one of two options. In the quantum version, each player controls a **qubit**(a quantum bit), which, instead of being just 0 or 1, can be in a **superposition** of both at once, like a coin spinning in the air before it lands.

More importantly, the two players' qubits can be **entangled**. Entanglement means the two qubits are linked in a way that has no classical equivalent: measuring one qubit instantly affects what you can expect from the other, regardless of how far apart they are. This shared connection changes which strategies are available and which outcomes the players can achieve.

The framework used here is the **Eisert-Wilkens-Lewenstein (EWL) protocol**, introduced in 1999. It works in three stages:

1. An **entanglement operator J(γ)** prepares a shared starting state. The parameter **γ (gamma)** controls how strongly the qubits are entangled. When γ = 0, the game is purely classical; at γ = π/2, the entanglement is at its maximum.
2. Each player applies their chosen **unitary strategy** (a quantum operation) to their own qubit.
3. A reverse entanglement step **J†** undoes the entanglement before the qubits are measured, and the **payoff** is calculated from the measurement probabilities.

At maximum entanglement, this opens up outcomes that no classical strategy can reach:

- In the Battle of the Sexes, the quantum equilibrium payoff reaches **2.5** (a **108% improvement**) over the classical mixed-strategy payoff of 1.2.
- In the Prisoner's Dilemma, both players can use a special quantum strategy called the **miracle move Q** (a phase-flip operation) to reliably land on the cooperative payoff of **3** (a **200% improvement**) over the classical confess-confess outcome of 1.

---

## NISQ Devices and Noise

A **NISQ (Noisy Intermediate-Scale Quantum) device** is a real quantum processor with enough qubits to run meaningful computations, but without the error correction that a fully fault-tolerant quantum computer would have. It is like doing arithmetic with a calculator whose buttons occasionally misfire. 

The sources of noise that matter here are:
- **Gate errors:** Quantum operations that are slightly wrong each time they are applied.
- **Readout errors:** The device reads out the wrong answer even when the computation itself was fine.
- **Amplitude damping (decoherence):** A qubit loses its quantum state before measurement, like a signal fading out.
- **Crosstalk:** When many circuits are run at the same time on adjacent qubits, the noise from one set of qubits bleeds into another.

All of these push the measured payoffs away from their theoretical values. This is why running a quantum game theory experiment on real hardware is hard: the noise makes it difficult to confirm any quantum advantage.

This project does not run on real hardware. Instead, it uses **Qiskit-Aer**, IBM's quantum circuit simulator, with a calibrated noise model that mimics a real superconducting processor. All simulator backends are seeded, so the results are fully reproducible: running the code twice yields identical output.

---

## Guided Circuit Mapping (GCM)

**Guided Circuit Mapping** is the error-mitigation technique introduced by Díaz Agreda et al. The idea is straightforward: instead of using whatever qubit pairs happen to be available, you profile the device to find which pairs have the lowest error, and then route each circuit to the best available pair. Keeping the pairs well separated also avoids crosstalk.

In this project, GCM is modelled as 31 qubit-pair **slots**, each with its own tracked error estimate. For every entanglement value, the circuit is sent to the slot with the lowest current error. After each run, the estimate for that slot is updated based on how much the result varied. This adaptive routing reduces the **Root-Mean-Square Error (RMSE)**, the typical gap between experimental and ideal payoffs, by 35 to 45% in the Battle of the Sexes and by 12 to 46% in the Prisoner's Dilemma.

A **paired t-test** is used to confirm that this reduction is not just numerical noise. For each strategy, the per-point absolute error without GCM is compared against the per-point absolute error with GCM across all 31 entanglement values. The test checks whether the average difference is zero. Every reduction in the Battle of the Sexes is significant at p < 10⁻⁷, and every reduction in the Prisoner's Dilemma is significant at p < 0.01.

---

## What This Project Does

This project has four components:

**1. Replicates the Battle of the Sexes.** The EWL protocol is run for four strategies (I, H, R(π/4), R(π)) across 31 entanglement values from γ = 0 to γ = π. The quantum equilibrium payoff of 2.5 is reproduced, matching the theoretical prediction.

**2. Models the GCM improvement.** Two conditions are compared: without GCM (extra crosstalk from dense circuit packing, mimicking what happens on a real device) and with GCM (adaptive low-error routing, no crosstalk). GCM consistently reduces the payoff error across all strategies.

**3. Extends to the Prisoner's Dilemma.** The original paper only covered the Battle of the Sexes. This project applies the same simulation and GCM pipeline to the Prisoner's Dilemma using the full EWL protocol, including the explicit disentanglement step J†. The miracle move Q is shown to reach the cooperative payoff of 3 at maximum entanglement.

**4. Runs the statistical test that the original paper deferred.** The original paper ran only 5 repetitions and flagged a formal statistical comparison as future work. This project raises the repetitions to 20 and runs the paired t-test, giving every result a proper significance value.

---

## Results

### Battle of the Sexes

Quantum equilibrium payoff: **2.50** at γ = π/2 — **108% over the classical baseline of 1.2.**

| Strategy | RMSE without GCM (Alice / Bob) | RMSE with GCM (Alice / Bob) | Reduction |
|----------|-------------------------------|----------------------------|-----------|
| I        | 0.0795 / 0.0783               | 0.0441 / 0.0467            | 45% / 40% |
| H        | 0.0561 / 0.0582               | 0.0361 / 0.0376            | 36% / 35% |
| R(π/4)   | 0.0673 / 0.0701               | 0.0403 / 0.0431            | 40% / 39% |
| R(π)     | 0.0810 / 0.0811               | 0.0479 / 0.0457            | 41% / 44% |

All paired t-tests: **p < 10⁻⁷.**

### Prisoner's Dilemma (extension)

Quantum miracle move (Q, Q) payoff: **3.00** at γ = π/2 — **200% over the classical Nash equilibrium of 1.**

| Strategy | RMSE without GCM (Alice / Bob) | RMSE with GCM (Alice / Bob) | Reduction |
|----------|-------------------------------|----------------------------|-----------|
| C        | 0.0105 / 0.0098               | 0.0088 / 0.0083            | 17% / 16% |
| D        | 0.0479 / 0.0386               | 0.0368 / 0.0328            | 23% / 15% |
| H        | 0.0456 / 0.0414               | 0.0245 / 0.0266            | 46% / 36% |
| Q        | 0.0121 / 0.0089               | 0.0106 / 0.0075            | 12% / 17% |

All paired t-tests: **p < 0.01.**

The absolute RMSE values here are lower than the 0.11–0.15 reported in the original paper on real hardware. This is because this project uses a simulated noise model rather than a live device. The relative GCM benefit is the meaningful point of comparison, and it holds in both cases.

---

## Repository Layout

```
quantum_common.py      noise model, GCM logic, RMSE calculation, t-test helpers
graph_helpers.py       all figure generation
run_all.py             entry point (runs both games and regenerates all figures)
requirements.txt       Python dependencies

BoS/
  quantum_BoS.py       Battle of the Sexes simulation
  graphs/              generated figures (regenerated on each run)

PD/
  quantum_PD.py        Prisoner's Dilemma simulation (the extension)
  graphs/              generated figures (regenerated on each run)
```

---

## How to Run

**Requirements:** Python 3.9 or later.

**Step 1 — Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 2 — Run everything**

```bash
python run_all.py
```

This runs both games end to end, prints all results to the terminal, and regenerates every figure into `BoS/graphs/` and `PD/graphs/`.

**Run individual games**

```bash
python BoS/quantum_BoS.py    # Battle of the Sexes only
python PD/quantum_PD.py      # Prisoner's Dilemma only
```

**What the terminal prints for each game:**
- The classical baseline (Nash equilibrium payoff)
- The quantum equilibrium payoff and percentage improvement
- A per-strategy RMSE table for the with-GCM condition
- A GCM vs. no-GCM comparison table with reduction percentages and paired t-test p-values

**Configuration** (edit `quantum_common.py`):

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `N_REPETITIONS` | 20 | number of independent runs per entanglement value |
| `N_SHOTS` | 2048 | measurement shots per circuit |
| `CROSSTALK_NO_GCM` | 0.02 | extra CNOT error in the without-GCM condition |

---

## References

- G. Díaz Agreda, C. A. Durán Paredes, M. Buenaventura Samboni, J. A. Andrade, S. Cajas Ordóñez, *"Bridging Theory and Practice in Quantum Game Theory: Optimized Implementation of the Battle of the Sexes with Error Mitigation on NISQ Hardware"*, IEEE Chilecon, 2023.
- J. Eisert, M. Wilkens, M. Lewenstein, *"Quantum Games and Quantum Strategies"*, Physical Review Letters 83(15), 1999.
