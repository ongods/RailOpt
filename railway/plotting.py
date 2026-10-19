"""Standalone scientific figures; plotting dependencies are optional for mechanics."""

from pathlib import Path
import os


def plot_matched(record, runs, route, output):
    """Compare saved/replayed states and distinct terminal energy flows."""
    os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib"))
    import matplotlib as mpl
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    import numpy as np

    with mpl.rc_context({"svg.fonttype": "none", "font.size": 9}):
        figure = Figure(figsize=(12, 8), layout="constrained")
        FigureCanvasAgg(figure)
        distance, time, energy, breakdown = figure.subplots(2, 2).flat
        for name, run in runs.items():
            distance.plot(run.states[0], run.states[1], label=name)
            time.plot(run.time_s, run.states[1], label=name)
            energy.plot(run.time_s, run.electrical.net_supply_energy_j / 3.6e6, label=name)
        x = [p[0] for p in route.speed_limits_mps] + [route.length_m]
        v = [p[1] for p in route.speed_limits_mps] + [route.speed_limits_mps[-1][1]]
        distance.step(x, v, where="post", color="black", linestyle=":", label="physical limit")
        distance.set(xlabel="Position (m)", ylabel="Speed (m/s)")
        time.set(xlabel="Time (s)", ylabel="Speed (m/s)")
        energy.set(xlabel="Time (s)", ylabel="Net train-terminal energy (kWh)")
        labels = ["Motoring", "Auxiliary", "Accepted regen", "Net supply"]
        for i, (name, run) in enumerate(runs.items()):
            e = run.electrical
            values = [e.motoring_energy_j[-1], e.auxiliary_energy_j[-1],
                      -e.regenerative_accepted_energy_j[-1], e.net_supply_energy_j[-1]]
            breakdown.bar(np.arange(4) + (i - 0.5) * 0.35, np.array(values) / 3.6e6,
                          width=0.35, label=name)
        breakdown.set_xticks(range(4), labels)
        breakdown.set_ylabel("Electrical energy (kWh); recovery negative")
        for ax in (distance, time, energy, breakdown):
            ax.grid(alpha=0.2)
            ax.legend()
        figure.suptitle(f"Synthetic matched-time profiles | {record['experiment_id']}\n"
                        "Hypothetical inputs; numerical verification only")
        for extension in ("png", "svg"):
            figure.savefig(output / f"comparison.{extension}", dpi=160)


def plot_energy_time(record, output: Path):
    # Use the ignored workspace cache by default in restricted environments.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".cache/matplotlib"))
    import matplotlib as mpl
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    feasible = [case for case in record["cases"] if case["status"] == "feasible"]
    frontier = sorted((case for case in feasible if case["on_sampled_frontier"]),
                      key=lambda case: case["summary"]["travel_time_s"])
    rejected = len(record["cases"]) - len(feasible)
    with mpl.rc_context({"svg.fonttype": "none", "font.size": 10}):
        figure = Figure(figsize=(11, 6), layout="constrained")
        FigureCanvasAgg(figure)
        ax = figure.add_subplot()
        if feasible:
            coast_cases = [case for case in feasible if case["control"]["coast_from_m"] is not None]
            if coast_cases:
                points = ax.scatter([case["summary"]["travel_time_s"] for case in coast_cases],
                                    [case["summary"]["electrical"]["net_supply_energy_j"] / 3.6e6 for case in coast_cases],
                                    c=[case["control"]["coast_from_m"] for case in coast_cases],
                                    cmap="viridis", s=42, alpha=0.85, label="Feasible coasting samples")
                figure.colorbar(points, ax=ax, label="Requested coast position (m)")
            dominated = [case for case in feasible if case["dominated_by"]]
            if dominated:
                ax.scatter([case["summary"]["travel_time_s"] for case in dominated],
                           [case["summary"]["electrical"]["net_supply_energy_j"] / 3.6e6 for case in dominated],
                           marker="x", color="#333333", s=32, linewidths=0.8, label="Dominated samples", zorder=3)
            ax.plot([case["summary"]["travel_time_s"] for case in frontier],
                    [case["summary"]["electrical"]["net_supply_energy_j"] / 3.6e6 for case in frontier],
                    color="#c04b24", linewidth=1.2, label="Sampled frontier (guide only)", zorder=1)
            for case in feasible:
                if case["case_id"] == "no_coast" or case["scenario_control"]:
                    x = case["summary"]["travel_time_s"]
                    y = case["summary"]["electrical"]["net_supply_energy_j"] / 3.6e6
                    label = "No-coast reference" if case["case_id"] == "no_coast" else f"Scenario coast: {case['control']['coast_from_m']:g} m"
                    ax.scatter([x], [y], marker="*", s=180, facecolors="#d6d6d6", edgecolors="#222222", zorder=4)
                    ax.annotate(label, (x, y), xytext=(12, 9), textcoords="offset points", fontsize=9)
            lowest = min(feasible, key=lambda case: case["summary"]["electrical"]["net_supply_energy_j"])
            if lowest["case_id"] != "no_coast" and not lowest["scenario_control"]:
                ax.annotate(f"Lowest sampled energy: coast at {lowest['control']['coast_from_m']:g} m",
                            (lowest["summary"]["travel_time_s"], lowest["summary"]["electrical"]["net_supply_energy_j"] / 3.6e6),
                            xytext=(0, 14), textcoords="offset points", ha="center", fontsize=9)
            ax.legend(loc="upper right")
            ax.margins(x=0.08, y=0.12)
        else:
            ax.text(0.5, 0.5, "No feasible profiles in the declared sweep", transform=ax.transAxes, ha="center")
        ax.set_xlabel("Journey time (s)")
        ax.set_ylabel("Net train-terminal energy (kWh)")
        ax.set_title("Coasting: synthetic energy-time tradeoff", loc="left", fontweight="bold")
        ax.grid(alpha=0.2)
        figure.suptitle(f"{len(feasible)} feasible; {rejected} rejected/excluded | benchmark {record['benchmark_id']}", fontsize=10)
        figure.text(0.5, -0.025, "Hypothetical inputs; different journey times. No equal-time savings or real-world validation claimed.",
                    ha="center", fontsize=9)
        for suffix in ("png", "svg"):
            figure.savefig(output / f"energy-time.{suffix}", dpi=180, bbox_inches="tight",
                           metadata={"Title": "Synthetic coasting energy-time benchmark",
                                     "Description": f"Benchmark {record['benchmark_id']}; hypothetical train-terminal energy."})
