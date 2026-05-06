"""Streamlit UI for Wrong-Way elevator frustration simulator."""

from __future__ import annotations

from dataclasses import replace
import io
import time

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle
import pandas as pd
import streamlit as st

from .analytics import build_frustration_heatmap, run_batch_for_observer
from .config import (
    BuildingRenderState,
    Event,
    ObserverConfig,
    RunResult,
    SimulationConfig,
    SubwayConfig,
    SubwayObserver,
)
from .elevator_mode import ElevatorSimulation, desired_direction
from .metrics import rage_score
from .subway_mode import SubwaySimulation
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
    st.session_state.setdefault("mode", "Elevator")
    st.session_state.setdefault("floors", 20)
    st.session_state.setdefault("elevators", 3)
    st.session_state.setdefault("start_floor", 10)
    st.session_state.setdefault("desired_direction", "up")
    st.session_state.setdefault("destination_floor", 11)
    st.session_state.setdefault("profile", "Morning Rush")
    st.session_state.setdefault("seed", 42)
    st.session_state.setdefault("subway_desired_direction", "up")
    st.session_state.setdefault("subway_seed", 42)


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


def _render_building_figure(
    state: BuildingRenderState,
    floors: int,
    ax: plt.Axes | None = None,
) -> plt.Figure:
    if ax is None:
        fig, ax = plt.subplots(figsize=(4.6, 6.4))
    else:
        # Reuse path: clear the existing axes and redraw onto the same figure.
        # Avoids per-tick figure allocation in the live playback loop.
        ax.clear()
        fig = ax.figure
    fig.patch.set_facecolor("#F4EBD0")
    ax.set_facecolor("#F8F2E4")

    elevators = state["elevators"]
    x_values = [e["elevator_id"] for e in elevators]
    observer_floor = state["observer_floor"]
    depth_x = 0.16
    depth_y = 0.28
    shaft_width = 0.56
    car_height = 0.82
    car_width = 0.4

    for shaft_id in x_values:
        left = shaft_id - shaft_width / 2
        back_panel = Polygon(
            [
                (left, -0.45),
                (left + shaft_width, -0.45),
                (left + shaft_width + depth_x, -0.45 + depth_y),
                (left + depth_x, -0.45 + depth_y),
            ],
            closed=True,
            facecolor="#E3D7BD",
            edgecolor="#A98F68",
            linewidth=1.0,
            zorder=0,
        )
        side_panel = Polygon(
            [
                (left + shaft_width, -0.45),
                (left + shaft_width, floors - 0.45),
                (left + shaft_width + depth_x, floors - 0.45 + depth_y),
                (left + shaft_width + depth_x, -0.45 + depth_y),
            ],
            closed=True,
            facecolor="#D0C0A3",
            edgecolor="#A98F68",
            linewidth=1.0,
            zorder=0,
        )
        front_panel = Rectangle(
            (left, -0.45),
            shaft_width,
            floors,
            facecolor="#F7F2E8",
            edgecolor="#A98F68",
            linewidth=1.2,
            zorder=1,
        )
        ax.add_patch(back_panel)
        ax.add_patch(side_panel)
        ax.add_patch(front_panel)

        for floor in range(floors):
            ax.plot(
                [left, left + shaft_width],
                [floor + 0.5, floor + 0.5],
                color="#D7CAB0",
                linewidth=0.5,
                zorder=2,
            )

    for e in elevators:
        base_x = e["elevator_id"] - car_width / 2
        base_y = e["floor"] - car_height / 2
        front_face = Rectangle(
            (base_x, base_y),
            car_width,
            car_height,
            facecolor="#2E86AB",
            edgecolor="#124559",
            linewidth=1.1,
            zorder=4,
        )
        side_face = Polygon(
            [
                (base_x + car_width, base_y),
                (base_x + car_width, base_y + car_height),
                (base_x + car_width + depth_x * 0.55, base_y + car_height + depth_y * 0.55),
                (base_x + car_width + depth_x * 0.55, base_y + depth_y * 0.55),
            ],
            closed=True,
            facecolor="#1F6F8B",
            edgecolor="#124559",
            linewidth=1.0,
            zorder=3,
        )
        top_face = Polygon(
            [
                (base_x, base_y + car_height),
                (base_x + car_width, base_y + car_height),
                (base_x + car_width + depth_x * 0.55, base_y + car_height + depth_y * 0.55),
                (base_x + depth_x * 0.55, base_y + car_height + depth_y * 0.55),
            ],
            closed=True,
            facecolor="#63B3D1",
            edgecolor="#124559",
            linewidth=1.0,
            zorder=5,
        )
        ax.add_patch(side_face)
        ax.add_patch(front_face)
        ax.add_patch(top_face)
        ax.text(
            e["elevator_id"] + 0.02,
            e["floor"] + 0.72,
            e["direction"],
            ha="center",
            va="bottom",
            fontsize=8,
            color="#3B2F2F",
            zorder=6,
        )

    ax.scatter([-1.05], [observer_floor], c="#D7263D", s=240, marker="*", zorder=6)
    ax.plot(
        [-0.7, x_values[-1] + 0.45],
        [observer_floor, observer_floor],
        color="#D7263D",
        linewidth=1.0,
        alpha=0.35,
        linestyle="--",
        zorder=2,
    )

    ax.set_xlim(-1.35, max(x_values) + 0.9)
    ax.set_ylim(-0.5, floors - 0.5)
    ax.set_yticks(list(range(0, floors, max(1, floors // 10))))
    ax.set_xlabel("Shaft")
    ax.set_ylabel("Floor")
    ax.set_title("Live Elevator State", color="#3B2F2F", pad=12)
    ax.grid(axis="y", alpha=0.12, color="#7A6A53")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#A98F68")
    ax.spines["bottom"].set_color("#A98F68")
    ax.tick_params(colors="#5C4B3A")
    ax.xaxis.label.set_color("#5C4B3A")
    ax.yaxis.label.set_color("#5C4B3A")
    ax.legend(
        handles=[
            Rectangle((0, 0), 1, 1, facecolor="#2E86AB", edgecolor="#124559", label="Elevators"),
            Line2D([0], [0], marker="*", color="w", label="Observer", markerfacecolor="#D7263D", markersize=12),
        ],
        loc="upper right",
        fontsize=8,
        frameon=False,
    )
    fig.tight_layout()
    return fig


def _render_heatmap(
    heatmap: dict[str, list[float]],
    title: str = "Frustration Heatmap (avg wrong-way encounters)",
    cbar_label: str | None = None,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 2.8))
    data = [heatmap["up"], heatmap["down"]]
    im = ax.imshow(data, aspect="auto", cmap="YlOrRd")
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Up", "Down"])
    ax.set_xlabel("Observer Floor")
    ax.set_title(title)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    if cbar_label:
        cbar.set_label(cbar_label)
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


def _render_subway_timeline(result: RunResult, max_wait: float) -> plt.Figure:
    """Horizontal timeline showing wrong-way and useful train arrivals."""

    fig, ax = plt.subplots(figsize=(10, 2.6))
    fig.patch.set_facecolor("#F4EBD0")
    ax.set_facecolor("#F8F2E4")

    ax.axvline(0, color="#D7263D", linestyle="--", alpha=0.7, label="You arrive")

    wrong_x = [
        e.timestamp for e in result.event_log if e.event_type == "stop" and e.is_wrong_way
    ]
    served_x = [e.timestamp for e in result.event_log if e.event_type == "served"]

    if wrong_x:
        ax.scatter(
            wrong_x,
            [0] * len(wrong_x),
            s=120,
            color="#F46036",
            marker="X",
            zorder=3,
            label="Wrong-way train",
        )
    if served_x:
        ax.scatter(
            served_x,
            [1] * len(served_x),
            s=180,
            color="#2E86AB",
            marker="o",
            zorder=3,
            label="Useful train",
        )
    if result.timed_out:
        ax.axvline(
            result.actual_wait_seconds,
            color="#7A6A53",
            linestyle=":",
            alpha=0.7,
            label="Timeout",
        )

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Other dir", "Your dir"])
    ax.set_xlabel("Seconds since you arrived")
    upper_x = max(max_wait, result.actual_wait_seconds * 1.05) if result.actual_wait_seconds > 0 else max_wait
    ax.set_xlim(-5, upper_x)
    ax.set_ylim(-0.7, 1.7)
    ax.set_title("Subway Arrivals Timeline")
    ax.grid(axis="x", alpha=0.2, color="#7A6A53")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    fig.tight_layout()
    return fig


def _prediction_caption(prediction: str, rigged_score: float) -> str:
    if prediction == "Definitely rigged" and rigged_score < 45:
        return "Prediction check: your outrage overshot the data. Respectfully."
    if prediction == "Pretty fair" and rigged_score > 60:
        return "Prediction check: optimism did not survive contact with events."
    return "Prediction check: your intuition and the run were broadly aligned."


def _format_event(event: Event) -> str:
    car = f" car {event.elevator_id}" if event.elevator_id is not None else ""
    floor = f" @ floor {event.floor}" if event.floor is not None else ""
    flag = " (wrong-way)" if event.is_wrong_way else ""
    return f"`t={event.timestamp:>5.1f}s` {event.event_type}{car}{floor}{flag}"


def _render_replay_panel(result: RunResult, floors: int) -> None:
    """Scrub-through replay of the most recent live run.

    Walks ``result.state_log`` (one entry per tick, captured at end of tick)
    and re-renders the building diagram for the selected snapshot. Recent
    events up to that timestamp are listed alongside so the user can see
    *what just happened* at any point.
    """

    if not result.state_log:
        return

    with st.expander("Replay this run", expanded=False):
        last_idx = len(result.state_log) - 1
        st.caption(
            f"Scrub through the {last_idx + 1} ticks of this run. "
            "0 is the moment you arrived; the final index is when you were served or timed out."
        )
        tick_idx = st.slider(
            "Tick",
            min_value=0,
            max_value=last_idx,
            value=last_idx,
            key="replay_tick",
        )
        state = result.state_log[tick_idx]

        replay_fig, replay_ax = plt.subplots(figsize=(4.6, 6.4))
        try:
            _render_building_figure(state, floors=floors, ax=replay_ax)
            chart_col, info_col = st.columns([1, 1])
            chart_col.pyplot(replay_fig)
            with info_col:
                st.metric("Sim time", f"{state['time']:.0f}s")
                ghost_total = state["wrong_way_passes"] + state["wrong_way_stops"]
                st.metric("Ghost Elevators so far", ghost_total)
                st.metric("Wrong-way streak so far", state["max_streak"])
                horizon = state["time"] + 1e-9
                relevant = [e for e in result.event_log if e.timestamp <= horizon]
                if relevant:
                    st.markdown("**Recent events**")
                    for event in relevant[-6:]:
                        st.markdown(f"- {_format_event(event)}")
                else:
                    st.caption("No events yet — observer just arrived.")
        finally:
            plt.close(replay_fig)


def _render_belief_trend() -> None:
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


def _render_subway_app() -> None:
    with st.sidebar:
        st.header("Subway Setup")
        st.radio(
            "Desired direction",
            options=["up", "down"],
            horizontal=True,
            key="subway_desired_direction",
        )
        desired_mean = st.slider(
            "Mean wait between desired-direction trains (s)",
            min_value=20,
            max_value=300,
            value=90,
            step=10,
        )
        other_mean = st.slider(
            "Mean wait between other-direction trains (s)",
            min_value=20,
            max_value=300,
            value=60,
            step=10,
        )
        max_wait = st.slider(
            "Max wait (s)",
            min_value=60,
            max_value=1200,
            value=600,
            step=60,
        )
        seed = st.number_input(
            "Seed",
            min_value=0,
            step=1,
            value=int(st.session_state.subway_seed),
            key="subway_seed",
        )
        run_subway = st.button("Run subway simulation", type="primary")

    config = SubwayConfig(
        desired_direction_rate=1.0 / float(desired_mean),
        other_direction_rate=1.0 / float(other_mean),
        max_wait_seconds=float(max_wait),
        seed=int(seed),
    )
    observer = SubwayObserver(desired_direction=st.session_state.subway_desired_direction)

    prediction = st.radio(
        "Prediction before reveal: how unfair will this feel?",
        ["Pretty fair", "Mildly cursed", "Definitely rigged"],
        horizontal=True,
        key="subway_prediction",
    )

    if run_subway:
        result = SubwaySimulation(config=config, observer=observer).run()
        wrong_way_total = result.wrong_way_stops
        tone_line = _tone_line(wrong_way_total, result.max_wrong_way_streak)

        st.subheader("Truth Screen")
        kpi_cols = st.columns(4)
        kpi_cols[0].metric("Actual Wait", f"{result.actual_wait_seconds:.0f}s")
        kpi_cols[1].metric("Perceived Wait", f"{result.perceived_wait_seconds:.0f}s")
        kpi_cols[2].metric("Ghost Trains", wrong_way_total)
        kpi_cols[3].metric("Rage Score", f"{result.rage_score:.0f}")

        st.info(tone_line)
        st.caption(_prediction_caption(prediction, result.rigged_system_belief_score))

        st.write("**Complaint Generator**")
        st.write(complaint_generator(result))
        st.write("**Statistical Rebuttal**")
        st.write(statistical_rebuttal(result))

        timeline_fig = _render_subway_timeline(result, max_wait=float(max_wait))
        st.pyplot(timeline_fig)
        plt.close(timeline_fig)

        st.session_state.rigged_history.append(result.rigged_system_belief_score)
        st.session_state.last_run = result
        # Subway runs have no state_log, so the replay panel auto-skips. Clear
        # any stale slider state from a prior elevator run for cleanliness.
        st.session_state.pop("replay_tick", None)


def render_app() -> None:
    st.set_page_config(page_title="Wrong-Way", page_icon="⬆️⬇️", layout="wide")
    _set_default_state()

    st.title("The Other Elevator Always Wins")
    st.caption("A frustration simulator for directional bias and the inspection paradox")

    with st.sidebar:
        st.selectbox("Mode", ["Elevator", "Subway"], key="mode")

    if st.session_state.mode == "Subway":
        _render_subway_app()
        _render_belief_trend()
        return

    with st.sidebar:
        st.header("Setup")
        preset = st.selectbox("Instructor quick scenario", list(PRESETS.keys()))
        if st.button("Apply scenario"):
            _apply_preset(preset)

        floors = st.slider("Floors", min_value=6, max_value=40, key="floors")
        elevators = st.slider("Elevators", min_value=1, max_value=8, key="elevators")
        if st.session_state.start_floor > floors - 1:
            st.session_state.start_floor = floors - 1
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

        live_fig, live_ax = plt.subplots(figsize=(4.6, 6.4))
        try:
            while not sim.done:
                has_step = sim.step()
                if not has_step:
                    break
                state = sim.current_state()
                _render_building_figure(state, floors=floors, ax=live_ax)
                chart_placeholder.pyplot(live_fig)

                rage = rage_score(
                    wrong_way_passes=state["wrong_way_passes"],
                    wrong_way_stops=state["wrong_way_stops"],
                    max_streak=state["max_streak"],
                )
                with stats_placeholder.container():
                    st.metric("Wait clock", f"{state['time']:.0f}s")
                    st.metric(
                        "Ghost Elevators",
                        state["wrong_way_passes"] + state["wrong_way_stops"],
                    )
                    st.metric("Wrong-way streak", state["max_streak"])
                    st.progress(min(100, int(rage)), text=f"Rage Meter: {rage:.0f}/100")

                if speed > 0:
                    time.sleep(speed)
        finally:
            plt.close(live_fig)

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
        st.session_state.last_run = result
        st.session_state.last_run_floors = floors
        # Reset replay slider so new runs default to "show the final tick".
        st.session_state.pop("replay_tick", None)

    if "last_run" in st.session_state and st.session_state.last_run.state_log:
        _render_replay_panel(
            st.session_state.last_run,
            st.session_state.last_run_floors,
        )

    _render_belief_trend()

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
        stat_cols[3].metric(
            f"Tail vs {summary.reference_profile}",
            f"{summary.tail_share_vs_balanced * 100:.1f}%",
            help=(
                f"Share of {summary.profile} runs whose wait exceeded the P90 wait "
                f"({summary.reference_p90_wait:.1f}s) of a parallel batch under "
                f"{summary.reference_profile} demand. Above 10% means your scenario "
                "produces tail-event waits more often than balanced demand would."
            ),
        )

        wait_fig = _render_wait_distribution(summary.actual_wait_seconds, summary.perceived_wait_seconds)
        st.pyplot(wait_fig)
        plt.close(wait_fig)

        streak_fig = _render_streak_distribution(summary.wrong_way_streaks)
        st.pyplot(streak_fig)
        plt.close(streak_fig)

        encounters_fig = _render_heatmap(
            heatmap.wrong_way_encounters,
            title="Frustration Heatmap (avg wrong-way encounters)",
            cbar_label="encounters",
        )
        st.pyplot(encounters_fig)
        plt.close(encounters_fig)

        inflation_fig = _render_heatmap(
            heatmap.perceived_wait_inflation,
            title="Perceived-Wait Inflation (avg perceived − actual seconds)",
            cbar_label="seconds",
        )
        st.pyplot(inflation_fig)
        plt.close(inflation_fig)

        sampled_sim = ElevatorSimulation(
            config=replace(config, seed=(config.seed or 0) + 999),
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
        screenshot_panel.write(
            f"Tail share vs {summary.reference_profile} "
            f"(>= {summary.reference_p90_wait:.1f}s): "
            f"{summary.tail_share_vs_balanced * 100:.1f}%\n"
        )
        st.code(screenshot_panel.getvalue())
