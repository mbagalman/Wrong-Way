"""Streamlit UI for Wrong-Way elevator frustration simulator."""

from __future__ import annotations

import io
import time

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from .analytics import build_frustration_heatmap, run_batch_for_observer
from .config import ObserverConfig, SimulationConfig
from .elevator_mode import ElevatorSimulation, desired_direction
from .metrics import rage_score
from .tone import TONE_PACK, complaint_generator, statistical_rebuttal

PRESETS = {
    "Custom": None,
    "Top Floor Going Up (Boundary Curse)": {
        "floors": 20,
        "elevators": 3,
        "start_floor": 18,
        "desired_direction": "up",
        "destination_floor": 19,
        "profile": "Morning Rush",
    },
    "Morning Rush to Lobby": {
        "floors": 20,
        "elevators": 3,
        "start_floor": 17,
        "desired_direction": "down",
        "destination_floor": 0,
        "profile": "Morning Rush",
    },
    "Penthouse Cruelty Demo": {
        "floors": 22,
        "elevators": 3,
        "start_floor": 20,
        "desired_direction": "up",
        "destination_floor": 21,
        "profile": "Penthouse Cruelty",
    },
}


def _set_default_state() -> None:
    st.session_state.setdefault("rigged_history", [])
    st.session_state.setdefault("floors", 20)
    st.session_state.setdefault("elevators", 3)
    st.session_state.setdefault("start_floor", 10)
    st.session_state.setdefault("desired_direction", "up")
    st.session_state.setdefault("destination_floor", 11)
    st.session_state.setdefault("profile", "Morning Rush")
    st.session_state.setdefault("seed", 42)


def _apply_preset(preset_name: str) -> None:
    preset = PRESETS.get(preset_name)
    if not preset:
        return
    for key, value in preset.items():
        st.session_state[key] = value


def _destination_options(floors: int, start_floor: int, direction: str) -> list[int]:
    if direction == "up":
        return list(range(start_floor + 1, floors))
    return list(range(0, start_floor))


def _render_building_figure(state: dict[str, object], floors: int) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(4.6, 6.4))

    elevators = state["elevators"]
    x_values = [e["elevator_id"] for e in elevators]
    y_values = [e["floor"] for e in elevators]

    ax.scatter(x_values, y_values, c="#2E86AB", s=190, label="Elevators")
    observer_floor = int(state["observer_floor"])
    ax.scatter([-1], [observer_floor], c="#D7263D", s=240, marker="*", label="Observer")

    for e in elevators:
        ax.text(
            e["elevator_id"],
            e["floor"] + 0.25,
            e["direction"],
            ha="center",
            va="bottom",
            fontsize=8,
        )

    ax.set_xlim(-1.6, max(x_values) + 1)
    ax.set_ylim(-0.5, floors - 0.5)
    ax.set_yticks(list(range(0, floors, max(1, floors // 10))))
    ax.set_xlabel("Shaft")
    ax.set_ylabel("Floor")
    ax.set_title("Live Elevator State")
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    return fig


def _render_heatmap(heatmap: dict[str, list[float]]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 2.8))
    data = [heatmap["up"], heatmap["down"]]
    im = ax.imshow(data, aspect="auto", cmap="YlOrRd")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Up", "Down"])
    ax.set_xlabel("Observer Floor")
    ax.set_title("Frustration Heatmap (avg wrong-way encounters)")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    return fig


def _render_wait_distribution(actual: list[float], perceived: list[float]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.8, 3.6))
    ax.hist(actual, bins=30, alpha=0.6, label="Actual wait")
    ax.hist(perceived, bins=30, alpha=0.6, label="Perceived wait")
    ax.set_xlabel("Seconds")
    ax.set_ylabel("Frequency")
    ax.set_title("Actual vs Perceived Wait Distribution")
    ax.legend()
    fig.tight_layout()
    return fig


def _render_streak_distribution(streaks: list[int]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.8, 3.4))
    buckets = {"0": 0, "1": 0, "2": 0, "3+": 0}
    for streak in streaks:
        if streak <= 2:
            buckets[str(streak)] += 1
        else:
            buckets["3+"] += 1
    ax.bar(list(buckets.keys()), list(buckets.values()), color="#F46036")
    ax.set_title("Wrong-Way Streak Distribution")
    ax.set_xlabel("Max streak before service")
    ax.set_ylabel("Runs")
    fig.tight_layout()
    return fig


def _tone_line(result_wrong_way_total: int, streak: int) -> str:
    idx = (result_wrong_way_total + streak) % len(TONE_PACK)
    return TONE_PACK[idx]


def render_app() -> None:
    st.set_page_config(page_title="Wrong-Way", page_icon="⬆️⬇️", layout="wide")
    _set_default_state()

    st.title("The Other Elevator Always Wins")
    st.caption("A frustration simulator for directional bias and the inspection paradox")

    with st.sidebar:
        st.header("Setup")
        preset = st.selectbox("Instructor quick scenario", list(PRESETS.keys()))
        if st.button("Apply scenario"):
            _apply_preset(preset)

        floors = st.slider("Floors", min_value=6, max_value=40, key="floors")
        elevators = st.slider("Elevators", min_value=1, max_value=8, key="elevators")
        st.slider("Observer floor", min_value=0, max_value=floors - 1, key="start_floor")
        st.radio("Desired direction", options=["up", "down"], horizontal=True, key="desired_direction")

        destination_candidates = _destination_options(
            floors,
            st.session_state.start_floor,
            st.session_state.desired_direction,
        )
        if not destination_candidates:
            st.session_state.desired_direction = "down" if st.session_state.start_floor == floors - 1 else "up"
            destination_candidates = _destination_options(
                floors,
                st.session_state.start_floor,
                st.session_state.desired_direction,
            )

        if st.session_state.destination_floor not in destination_candidates:
            st.session_state.destination_floor = destination_candidates[0]

        st.selectbox(
            "Destination floor",
            options=destination_candidates,
            key="destination_floor",
        )

        st.selectbox(
            "Demand profile",
            options=["Morning Rush", "Evening Return", "Random Midday", "Penthouse Cruelty"],
            key="profile",
        )

        seed = st.number_input("Seed", min_value=0, step=1, value=int(st.session_state.seed))
        tick_seconds = st.slider("Tick seconds", min_value=0.25, max_value=2.0, value=1.0, step=0.25)
        speed = st.slider("Live playback delay (seconds)", min_value=0.0, max_value=0.25, value=0.02, step=0.01)
        batch_trials = st.number_input("Batch trials", min_value=1000, max_value=10000, value=1000, step=250)

        run_live = st.button("Run live simulation", type="primary")
        run_batch = st.button("Run batch analytics")

    desired_dir = desired_direction(st.session_state.start_floor, st.session_state.destination_floor)
    observer = ObserverConfig(
        start_floor=st.session_state.start_floor,
        destination_floor=st.session_state.destination_floor,
        desired_direction=desired_dir,
    )

    config = SimulationConfig(
        floors=floors,
        elevators=elevators,
        tick_seconds=tick_seconds,
        max_wait_seconds=240.0,
        seed=int(seed),
    )

    prediction = st.radio(
        "Prediction before reveal: how unfair will this feel?",
        ["Pretty fair", "Mildly cursed", "Definitely rigged"],
        horizontal=True,
    )

    if run_live:
        sim = ElevatorSimulation(config=config, observer=observer, profile=st.session_state.profile)
        live_col, stats_col = st.columns([2, 1])
        chart_placeholder = live_col.empty()
        stats_placeholder = stats_col.empty()

        while not sim.done:
            has_step = sim.step()
            if not has_step:
                break
            state = sim.current_state()
            fig = _render_building_figure(state, floors=floors)
            chart_placeholder.pyplot(fig)
            plt.close(fig)

            rage = rage_score(
                wrong_way_passes=state["wrong_way_passes"],
                wrong_way_stops=state["wrong_way_stops"],
                max_streak=state["max_streak"],
            )
            with stats_placeholder.container():
                st.metric("Wait clock", f"{state['time']:.0f}s")
                st.metric("Ghost Elevators", int(state["wrong_way_passes"]) + int(state["wrong_way_stops"]))
                st.metric("Wrong-way streak", int(state["max_streak"]))
                st.progress(min(100, int(rage)), text=f"Rage Meter: {rage:.0f}/100")

            if speed > 0:
                time.sleep(speed)

        result = sim.run()
        wrong_way_total = result.wrong_way_passes + result.wrong_way_stops
        tone_line = _tone_line(wrong_way_total, result.max_wrong_way_streak)

        st.subheader("Truth Screen")
        kpi_cols = st.columns(4)
        kpi_cols[0].metric("Actual Wait", f"{result.actual_wait_seconds:.0f}s")
        kpi_cols[1].metric("Perceived Wait", f"{result.perceived_wait_seconds:.0f}s")
        kpi_cols[2].metric("Ghost Encounters", wrong_way_total)
        kpi_cols[3].metric("Rage Score", f"{result.rage_score:.0f}")

        st.info(tone_line)

        if prediction == "Definitely rigged" and result.rigged_system_belief_score < 45:
            st.caption("Prediction check: your outrage overshot the data. Respectfully.")
        elif prediction == "Pretty fair" and result.rigged_system_belief_score > 60:
            st.caption("Prediction check: optimism did not survive contact with events.")
        else:
            st.caption("Prediction check: your intuition and the run were broadly aligned.")

        st.write("**Complaint Generator**")
        st.write(complaint_generator(result))
        st.write("**Statistical Rebuttal**")
        st.write(statistical_rebuttal(result))

        st.write("**Arrival Snapshot (cars when you started waiting)**")
        st.dataframe(pd.DataFrame(result.arrival_snapshot), use_container_width=True)

        st.session_state.rigged_history.append(result.rigged_system_belief_score)

    st.subheader("Rigged Belief Trend")
    if st.session_state.rigged_history:
        trend_df = pd.DataFrame(
            {
                "run": list(range(1, len(st.session_state.rigged_history) + 1)),
                "rigged_belief": st.session_state.rigged_history,
            }
        )
        st.line_chart(trend_df.set_index("run"))
    if st.button("Reset belief trend"):
        st.session_state.rigged_history = []
        st.rerun()

    if run_batch:
        with st.spinner("Running batch analytics..."):
            summary = run_batch_for_observer(
                config=config,
                observer=observer,
                profile=st.session_state.profile,
                trials=int(batch_trials),
            )
            trials_per_cell = max(20, int(batch_trials) // max(1, floors * 2))
            heatmap = build_frustration_heatmap(
                config=config,
                profile=st.session_state.profile,
                trials_per_cell=trials_per_cell,
            )

        st.subheader("Batch Analytics")
        stat_cols = st.columns(4)
        stat_cols[0].metric("Runs", summary.run_count)
        stat_cols[1].metric("P50 wait", f"{summary.percentile_p50_wait:.1f}s")
        stat_cols[2].metric("P90 wait", f"{summary.percentile_p90_wait:.1f}s")
        stat_cols[3].metric("Long-gap hit rate", f"{summary.long_gap_hit_rate * 100:.1f}%")

        wait_fig = _render_wait_distribution(summary.actual_wait_seconds, summary.perceived_wait_seconds)
        st.pyplot(wait_fig)
        plt.close(wait_fig)

        streak_fig = _render_streak_distribution(summary.wrong_way_streaks)
        st.pyplot(streak_fig)
        plt.close(streak_fig)

        heatmap_fig = _render_heatmap(heatmap)
        st.pyplot(heatmap_fig)
        plt.close(heatmap_fig)

        sampled_sim = ElevatorSimulation(
            config=SimulationConfig(
                floors=config.floors,
                elevators=config.elevators,
                tick_seconds=config.tick_seconds,
                max_wait_seconds=config.max_wait_seconds,
                seed=(config.seed or 0) + 999,
                travel_time_per_floor=config.travel_time_per_floor,
                door_dwell_seconds=config.door_dwell_seconds,
                perceived_coeffs=config.perceived_coeffs,
            ),
            observer=observer,
            profile=st.session_state.profile,
        )
        sampled_result = sampled_sim.run()
        st.write("**System Snapshot at Arrival (sampled run)**")
        st.dataframe(pd.DataFrame(sampled_result.arrival_snapshot), use_container_width=True)

        export_df = pd.DataFrame(
            {
                "actual_wait_seconds": summary.actual_wait_seconds,
                "perceived_wait_seconds": summary.perceived_wait_seconds,
                "wrong_way_streak": summary.wrong_way_streaks,
                "wrong_way_passes": summary.wrong_way_passes,
                "wrong_way_stops": summary.wrong_way_stops,
            }
        )
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download classroom summary CSV",
            data=csv_bytes,
            file_name="wrong_way_batch_summary.csv",
            mime="text/csv",
        )

        st.write("**Screenshot-Friendly Summary Panel**")
        screenshot_panel = io.StringIO()
        screenshot_panel.write(f"Profile: {summary.profile}\n")
        screenshot_panel.write(f"Runs: {summary.run_count}\n")
        screenshot_panel.write(f"P50 wait: {summary.percentile_p50_wait:.1f}s\n")
        screenshot_panel.write(f"P90 wait: {summary.percentile_p90_wait:.1f}s\n")
        screenshot_panel.write(f"P95 wait: {summary.percentile_p95_wait:.1f}s\n")
        screenshot_panel.write(f"Long-gap hit rate: {summary.long_gap_hit_rate * 100:.1f}%\n")
        st.code(screenshot_panel.getvalue())
