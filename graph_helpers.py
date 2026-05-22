"""Plotting helpers used by the quantum game runners.

These persist the figures stored in BoS/graphs/ and PD/graphs/:
analytical payoff curves, the without-GCM overview (Fig. 4 style), per-strategy
payoffs with 95% confidence bands (Figs. 5-8 style), multi-run overlays
(Fig. 9 style), the per-strategy RMSE bars (Table II), and the GCM-vs-no-GCM
RMSE comparison that quantifies the improvement.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _ensure_dir(out_path: str):
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)


def save_payoff_curves(analytical: dict, out_path: str, gamma=None, title: str = "Analytical payoffs"):
    _ensure_dir(out_path)
    plt.figure(figsize=(8, 5))
    for s, (ea, eb) in analytical.items():
        x = gamma if gamma is not None else range(len(ea))
        plt.plot(x, ea, label=f"EA: {s}")
        plt.plot(x, eb, '--', label=f"EB: {s}")
    plt.xlabel('γ' if gamma is not None else 'γ index')
    plt.ylabel('Expected payoff')
    plt.title(title)
    plt.legend(fontsize='small')
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def save_rmse_bar(summary: dict, out_path: str, title: str = "RMSE per strategy (with GCM)"):
    _ensure_dir(out_path)
    strategies = list(summary.keys())
    rmse_ea = [summary[s]['rmse_ea'] for s in strategies]
    rmse_eb = [summary[s]['rmse_eb'] for s in strategies]

    x = range(len(strategies))
    width = 0.35
    plt.figure(figsize=(8, 4))
    plt.bar([i - width / 2 for i in x], rmse_ea, width=width, label='RMSE EA')
    plt.bar([i + width / 2 for i in x], rmse_eb, width=width, label='RMSE EB')
    plt.xticks(list(x), strategies)
    plt.ylabel('RMSE')
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def save_rmse_comparison(compare_rows: dict, strategies, out_path: str,
                         title: str = "RMSE: without GCM vs with GCM"):
    """Grouped bars contrasting mean RMSE (avg of EA, EB) per strategy."""
    _ensure_dir(out_path)
    base = [(compare_rows[s]['base_rmse_ea'] + compare_rows[s]['base_rmse_eb']) / 2 for s in strategies]
    gcm = [(compare_rows[s]['gcm_rmse_ea'] + compare_rows[s]['gcm_rmse_eb']) / 2 for s in strategies]

    x = range(len(strategies))
    width = 0.35
    plt.figure(figsize=(8, 4.5))
    plt.bar([i - width / 2 for i in x], base, width=width, label='without GCM', color='#d1495b')
    plt.bar([i + width / 2 for i in x], gcm, width=width, label='with GCM', color='#2e86ab')
    plt.xticks(list(x), strategies)
    plt.ylabel('Mean RMSE (EA, EB)')
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def save_payoff_with_ci(gamma, EA_exp, EB_exp, ci_ea, ci_eb, EA_ana, EB_ana,
                        out_path: str, title: str = "Payoff vs γ"):
    """Per-strategy experimental payoffs with 95% CI bands and analytical overlay."""
    _ensure_dir(out_path)
    gamma = np.asarray(gamma)
    plt.figure(figsize=(8, 5))

    plt.plot(gamma, EA_ana, color='#2e86ab', label='EA analytical')
    plt.plot(gamma, EB_ana, color='#d1495b', label='EB analytical')

    plt.plot(gamma, EA_exp, 'o', ms=3, color='#2e86ab', label='EA experimental')
    plt.fill_between(gamma, ci_ea[0], ci_ea[1], color='#2e86ab', alpha=0.2)
    plt.plot(gamma, EB_exp, 's', ms=3, color='#d1495b', label='EB experimental')
    plt.fill_between(gamma, ci_eb[0], ci_eb[1], color='#d1495b', alpha=0.2)

    plt.xlabel('γ (entanglement parameter)')
    plt.ylabel('Expected payoff')
    plt.title(title)
    plt.legend(fontsize='small')
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def save_no_gcm_overview(base_summary: dict, analytical: dict, strategies, gamma,
                         out_path: str, title: str = "Without GCM: payoffs vs γ"):
    """Fig. 4 style: experimental means (no GCM) against analytical curves."""
    _ensure_dir(out_path)
    gamma = np.asarray(gamma)
    n = len(strategies)
    ncols = 2
    nrows = (n + 1) // 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(11, 3.2 * nrows), squeeze=False)
    for k, s in enumerate(strategies):
        ax = axes[k // ncols][k % ncols]
        EA_ana, EB_ana = analytical[s]
        ax.plot(gamma, EA_ana, color='#2e86ab')
        ax.plot(gamma, EB_ana, color='#d1495b')
        ax.plot(gamma, base_summary[s]['EA_exp'], 'o', ms=3, color='#2e86ab', alpha=0.7)
        ax.plot(gamma, base_summary[s]['EB_exp'], 's', ms=3, color='#d1495b', alpha=0.7)
        ax.set_title(f"Strategy {s}")
        ax.set_xlabel('γ')
        ax.set_ylabel('payoff')
    for k in range(n, nrows * ncols):
        axes[k // ncols][k % ncols].axis('off')
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def save_multiple_runs(res_list, EA_ana, EB_ana, gamma, out_path: str,
                       title: str = "Multiple runs vs γ"):
    """Fig. 9 style: every individual repetition overlaid on the analytical curve."""
    _ensure_dir(out_path)
    gamma = np.asarray(gamma)
    all_EA = np.vstack([r["all_EA"] for r in res_list])  # (n_gamma, n_reps)
    all_EB = np.vstack([r["all_EB"] for r in res_list])
    n_reps = all_EA.shape[1]

    plt.figure(figsize=(8, 5))
    for r in range(n_reps):
        plt.plot(gamma, all_EA[:, r], color='#2e86ab', alpha=0.25, lw=0.8)
        plt.plot(gamma, all_EB[:, r], color='#d1495b', alpha=0.25, lw=0.8)
    plt.plot(gamma, EA_ana, color='#2e86ab', lw=2, label='EA analytical')
    plt.plot(gamma, EB_ana, color='#d1495b', lw=2, label='EB analytical')
    plt.xlabel('γ (entanglement parameter)')
    plt.ylabel('Expected payoff')
    plt.title(title)
    plt.legend(fontsize='small')
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()
