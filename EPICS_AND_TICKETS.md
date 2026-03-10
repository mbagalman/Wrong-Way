# Wrong-Way: Repo Bootstrap + Elevator MVP Ticket Plan

## Summary
- Build a Python repo for **Wrong-Way** with a Streamlit MVP focused on **Elevator Mode** first.
- Deliver a frustration simulator that tracks **actual wait** and **perceived wait** with dryly funny educational feedback.
- Ship in phases: bootstrap, core simulation, elevator behavior, live UI, analytics, and classroom polish; keep Subway Mode as V2.

## Implementation Contract
- `SimulationConfig`: `floors`, `elevators`, `tick_seconds`, `max_wait_seconds`, `seed`, `travel_time_per_floor`, `door_dwell_seconds`, `perceived_coeffs`.
- `ObserverConfig`: `start_floor`, `destination_floor`, `arrival_time`, `desired_direction`.
- `Event`: `timestamp`, `event_type`, `elevator_id`, `floor`, `direction`, `is_wrong_way`, `is_stop`.
- `RunResult`: `actual_wait_seconds`, `perceived_wait_seconds`, `wrong_way_passes`, `wrong_way_stops`, `max_wrong_way_streak`, `rage_score`, `event_log`.
- `BatchSummary`: percentile stats, wait distributions, wrong-way distributions, floor heatmap matrix.

Perceived wait formula (MVP):

`perceived_wait = actual_wait + a*(wrong_way_passes) + b*(wrong_way_stops) + c*(max_streak^2)`

Defaults: `a=8`, `b=18`, `c=6`.

## E0: Repository & Delivery Foundation
1. `T0.1` Initialize git repo and baseline structure.
2. `T0.2` Add Python project config and dependencies.
3. `T0.3` Add test/lint workflow and CI.
4. `T0.4` Create contributor/dev guide.
5. `T0.5` Create and maintain this `EPICS_AND_TICKETS.md` artifact.

## E1: Core Simulation Engine
1. `T1.1` Simulation clock + event queue.
2. `T1.2` Typed entities with validation.
3. `T1.3` Event logging and run result assembly.
4. `T1.4` Seeded reproducibility.
5. `T1.5` Perceived wait and rage metrics.

## E2: Elevator Mode Mechanics (MVP)
1. `T2.1` SCAN/sweep movement and stopping.
2. `T2.2` Wrong-way detection for pass-by and stop events.
3. `T2.3` Morning Rush / Evening Return / Random Midday profiles.
4. `T2.4` Penthouse Cruelty profile.
5. `T2.5` Served vs timeout outcomes.

## E3: Streamlit Live Experience
1. `T3.1` Vertical building live view with observer marker.
2. `T3.2` Ghost counter, wait clock, rage meter.
3. `T3.3` User-configurable controls.
4. `T3.4` Post-run truth screen.
5. `T3.5` Dryly funny classroom-safe tone pack.

## E4: Analytics & Teaching Visuals
1. `T4.1` Batch mode for >=1000 trials.
2. `T4.2` Frustration heatmap by floor and direction.
3. `T4.3` Actual vs perceived wait distributions.
4. `T4.4` Wrong-way streak distribution.
5. `T4.5` Arrival snapshot explainer panel.

## E5: Creative Classroom Enhancements
1. `T5.1` Prediction-before-reveal prompt.
2. `T5.2` Complaint generator + immediate rebuttal.
3. `T5.3` Rigged belief trend and reset.
4. `T5.4` Instructor quick scenarios.
5. `T5.5` CSV export + screenshot-friendly summary panel.

## E6: V2 Backlog
1. `T6.1` Subway mode.
2. `T6.2` God Mode overlay.
3. `T6.3` Replay mode.
4. `T6.4` Achievement badges.
5. `T6.5` Non-Poisson service experiments.
