"""Frozen official AEOSSP verifier (AstroAgentBench benchmarks/aeossp_standard/verifier), merged into one file."""
from __future__ import annotations
# ===== from aab_verifier/models.py (unchanged) =====
"""Data models for the aeossp_standard verifier."""


from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json

import numpy as np


NUMERICAL_EPS = 1.0e-9


@dataclass(frozen=True)
class Mission:
    case_id: str
    horizon_start: datetime
    horizon_end: datetime
    action_time_step_s: int
    geometry_sample_step_s: int
    resource_sample_step_s: int

    @property
    def horizon_seconds(self) -> int:
        seconds = (self.horizon_end - self.horizon_start).total_seconds()
        if seconds < 0:
            raise ValueError("mission horizon_end must be after horizon_start")
        if abs(seconds - round(seconds)) > NUMERICAL_EPS:
            raise ValueError("mission horizon must be an integer number of seconds")
        return int(round(seconds))


@dataclass(frozen=True)
class Sensor:
    sensor_type: str


@dataclass(frozen=True)
class AttitudeModel:
    max_slew_velocity_deg_per_s: float
    max_slew_acceleration_deg_per_s2: float
    settling_time_s: float
    max_off_nadir_deg: float


@dataclass(frozen=True)
class ResourceModel:
    battery_capacity_wh: float
    initial_battery_wh: float
    idle_power_w: float
    imaging_power_w: float
    slew_power_w: float
    sunlit_charge_power_w: float


@dataclass(frozen=True)
class SatelliteDef:
    satellite_id: str
    norad_catalog_id: int
    tle_line1: str
    tle_line2: str
    sensor: Sensor
    attitude_model: AttitudeModel
    resource_model: ResourceModel


@dataclass(frozen=True)
class TaskDef:
    task_id: str
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    release_time: datetime
    due_time: datetime
    required_duration_s: int
    required_sensor_type: str
    weight: float
    target_ecef_m: np.ndarray


@dataclass(frozen=True)
class AeosspCase:
    case_dir: Path
    mission: Mission
    satellites: dict[str, SatelliteDef]
    tasks: dict[str, TaskDef]


@dataclass(frozen=True)
class ObservationAction:
    satellite_id: str
    task_id: str
    start_time: datetime
    end_time: datetime

    @property
    def duration_s(self) -> int:
        seconds = (self.end_time - self.start_time).total_seconds()
        if abs(seconds - round(seconds)) > NUMERICAL_EPS:
            raise ValueError("Action duration must be an integer number of seconds")
        return int(round(seconds))


@dataclass(frozen=True)
class AeosspSolution:
    actions: list[ObservationAction]


@dataclass(frozen=True)
class ActionFailure:
    action_index: int
    satellite_id: str
    task_id: str
    reason: str
    stage: str
    time: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_index": self.action_index,
            "satellite_id": self.satellite_id,
            "task_id": self.task_id,
            "reason": self.reason,
            "stage": self.stage,
            "time": self.time.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if self.time is not None
            else None,
        }


@dataclass(frozen=True)
class ManeuverWindow:
    action_index: int
    satellite_id: str
    start_time: datetime
    end_time: datetime
    required_gap_s: float
    slew_angle_deg: float
    from_action_index: int | None
    from_task_id: str | None
    to_task_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_index": self.action_index,
            "satellite_id": self.satellite_id,
            "start_time": self.start_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "end_time": self.end_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "required_gap_s": self.required_gap_s,
            "slew_angle_deg": self.slew_angle_deg,
            "from_action_index": self.from_action_index,
            "from_task_id": self.from_task_id,
            "to_task_id": self.to_task_id,
        }


@dataclass(frozen=True)
class ValidatedAction:
    action_index: int
    satellite_id: str
    task_id: str
    start_time: datetime
    end_time: datetime

    @property
    def duration_s(self) -> int:
        seconds = (self.end_time - self.start_time).total_seconds()
        return int(round(seconds))

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_index": self.action_index,
            "satellite_id": self.satellite_id,
            "task_id": self.task_id,
            "start_time": self.start_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "end_time": self.end_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "duration_s": self.duration_s,
        }


@dataclass(frozen=True)
class TaskOutcome:
    task_id: str
    completed: bool
    completion_time: datetime | None
    completed_by_action_index: int | None
    weight: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "completed": self.completed,
            "completion_time": self.completion_time.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if self.completion_time is not None
            else None,
            "completed_by_action_index": self.completed_by_action_index,
            "weight": self.weight,
        }


@dataclass(frozen=True)
class BatteryTraceSegment:
    satellite_id: str
    start_time: datetime
    end_time: datetime
    battery_start_wh: float
    battery_end_wh: float
    load_power_w: float
    charge_power_w: float
    mode: str
    active_action_index: int | None
    active_task_id: str | None
    active_maneuver_to_action_index: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "satellite_id": self.satellite_id,
            "start_time": self.start_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "end_time": self.end_time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "battery_start_wh": self.battery_start_wh,
            "battery_end_wh": self.battery_end_wh,
            "load_power_w": self.load_power_w,
            "charge_power_w": self.charge_power_w,
            "mode": self.mode,
            "active_action_index": self.active_action_index,
            "active_task_id": self.active_task_id,
            "active_maneuver_to_action_index": self.active_maneuver_to_action_index,
        }


@dataclass(frozen=True)
class TimelineEvent:
    time: datetime
    satellite_id: str
    kind: str
    action_index: int | None = None
    task_id: str | None = None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "time": self.time.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "satellite_id": self.satellite_id,
            "kind": self.kind,
            "action_index": self.action_index,
            "task_id": self.task_id,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    metrics: dict[str, Any]
    violations: list[str]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "metrics": self.metrics,
            "violations": self.violations,
            "diagnostics": self.diagnostics,
        }

    def __str__(self) -> str:  # pragma: no cover - convenience helper
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass(frozen=True)
class SolutionAnalysis:
    case: AeosspCase
    solution: AeosspSolution
    result: VerificationResult
    validated_actions: tuple[ValidatedAction, ...]
    action_failures: tuple[ActionFailure, ...]
    maneuver_windows: tuple[ManeuverWindow, ...]
    task_outcomes: dict[str, TaskOutcome]
    battery_traces: dict[str, tuple[BatteryTraceSegment, ...]] = field(repr=False)
    per_satellite_resource_summary: dict[str, Any]
    timeline_events: tuple[TimelineEvent, ...]
    snapshot_candidates: tuple[datetime, ...]

# ===== from aab_verifier/io.py (unchanged) =====
"""Case and solution loading for the aeossp_standard verifier."""


from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import json

import brahe
import yaml



def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso_utc(value: str, *, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO 8601 timestamp string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include timezone information")
    return parsed.astimezone(UTC)


def _require_mapping(payload: Any, context: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{context} must be a mapping/object")
    return payload


def _require_list(payload: Any, context: str) -> list[Any]:
    if not isinstance(payload, list):
        raise ValueError(f"{context} must be a list/array")
    return payload


def _require_str(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def _require_int(mapping: dict[str, Any], key: str, context: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{context}.{key} must be an integer")
    return value


def _require_float(mapping: dict[str, Any], key: str, context: str) -> float:
    value = mapping.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{context}.{key} must be numeric")
    return float(value)


def _validate_positive_int(value: int, *, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")


def _validate_non_negative(value: float, *, field_name: str) -> None:
    if value < -NUMERICAL_EPS:
        raise ValueError(f"{field_name} must be >= 0")


def _is_aligned(seconds: float, step_s: int) -> bool:
    return abs((seconds / step_s) - round(seconds / step_s)) <= 1.0e-9


def _validate_horizon_divisibility(mission: Mission) -> None:
    for field_name, step_s in (
        ("action_time_step_s", mission.action_time_step_s),
        ("geometry_sample_step_s", mission.geometry_sample_step_s),
        ("resource_sample_step_s", mission.resource_sample_step_s),
    ):
        if not _is_aligned(float(mission.horizon_seconds), step_s):
            raise ValueError(
                f"mission horizon must be exactly divisible by {field_name}"
            )


def _task_target_ecef_m(task: dict[str, Any], context: str):
    return brahe.position_geodetic_to_ecef(
        [
            _require_float(task, "longitude_deg", context),
            _require_float(task, "latitude_deg", context),
            _require_float(task, "altitude_m", context),
        ],
        brahe.AngleFormat.DEGREES,
    )


def load_case(case_dir: str | Path) -> AeosspCase:
    case_path = Path(case_dir).resolve()
    mission_doc = _require_mapping(_load_yaml(case_path / "mission.yaml"), "mission.yaml")
    satellites_doc = _require_mapping(
        _load_yaml(case_path / "satellites.yaml"), "satellites.yaml"
    )
    tasks_doc = _require_mapping(_load_yaml(case_path / "tasks.yaml"), "tasks.yaml")

    mission_raw = _require_mapping(mission_doc.get("mission"), "mission.yaml.mission")
    satellites_raw = _require_list(
        satellites_doc.get("satellites"), "satellites.yaml.satellites"
    )
    tasks_raw = _require_list(tasks_doc.get("tasks"), "tasks.yaml.tasks")

    mission = Mission(
        case_id=_require_str(mission_raw, "case_id", "mission.yaml.mission"),
        horizon_start=_parse_iso_utc(
            _require_str(mission_raw, "horizon_start", "mission.yaml.mission"),
            field_name="mission.horizon_start",
        ),
        horizon_end=_parse_iso_utc(
            _require_str(mission_raw, "horizon_end", "mission.yaml.mission"),
            field_name="mission.horizon_end",
        ),
        action_time_step_s=_require_int(
            mission_raw, "action_time_step_s", "mission.yaml.mission"
        ),
        geometry_sample_step_s=_require_int(
            mission_raw, "geometry_sample_step_s", "mission.yaml.mission"
        ),
        resource_sample_step_s=_require_int(
            mission_raw, "resource_sample_step_s", "mission.yaml.mission"
        ),
    )
    if mission.horizon_end <= mission.horizon_start:
        raise ValueError("mission.horizon_end must be after mission.horizon_start")
    _validate_positive_int(mission.action_time_step_s, field_name="mission.action_time_step_s")
    _validate_positive_int(
        mission.geometry_sample_step_s, field_name="mission.geometry_sample_step_s"
    )
    _validate_positive_int(
        mission.resource_sample_step_s, field_name="mission.resource_sample_step_s"
    )
    _validate_horizon_divisibility(mission)

    propagation = _require_mapping(mission_raw.get("propagation"), "mission.yaml.mission.propagation")
    if _require_str(propagation, "model", "mission.yaml.mission.propagation") != "sgp4":
        raise ValueError("mission.propagation.model must be 'sgp4'")

    satellites: dict[str, SatelliteDef] = {}
    for index, payload in enumerate(satellites_raw):
        context = f"satellites.yaml.satellites[{index}]"
        sat_raw = _require_mapping(payload, context)
        sat_id = _require_str(sat_raw, "satellite_id", context)
        if sat_id in satellites:
            raise ValueError(f"Duplicate satellite_id: {sat_id}")
        tle_line1 = _require_str(sat_raw, "tle_line1", context)
        tle_line2 = _require_str(sat_raw, "tle_line2", context)
        if not brahe.validate_tle_lines(tle_line1, tle_line2):
            raise ValueError(f"{context} contains an invalid TLE pair")
        sensor_raw = _require_mapping(sat_raw.get("sensor"), f"{context}.sensor")
        attitude_raw = _require_mapping(sat_raw.get("attitude_model"), f"{context}.attitude_model")
        resource_raw = _require_mapping(sat_raw.get("resource_model"), f"{context}.resource_model")
        sensor = Sensor(sensor_type=_require_str(sensor_raw, "sensor_type", f"{context}.sensor"))
        if sensor.sensor_type not in {"visible", "infrared"}:
            raise ValueError(f"{context}.sensor.sensor_type must be 'visible' or 'infrared'")
        attitude = AttitudeModel(
            max_slew_velocity_deg_per_s=_require_float(
                attitude_raw, "max_slew_velocity_deg_per_s", f"{context}.attitude_model"
            ),
            max_slew_acceleration_deg_per_s2=_require_float(
                attitude_raw,
                "max_slew_acceleration_deg_per_s2",
                f"{context}.attitude_model",
            ),
            settling_time_s=_require_float(
                attitude_raw, "settling_time_s", f"{context}.attitude_model"
            ),
            max_off_nadir_deg=_require_float(
                attitude_raw, "max_off_nadir_deg", f"{context}.attitude_model"
            ),
        )
        resource = ResourceModel(
            battery_capacity_wh=_require_float(
                resource_raw, "battery_capacity_wh", f"{context}.resource_model"
            ),
            initial_battery_wh=_require_float(
                resource_raw, "initial_battery_wh", f"{context}.resource_model"
            ),
            idle_power_w=_require_float(resource_raw, "idle_power_w", f"{context}.resource_model"),
            imaging_power_w=_require_float(
                resource_raw, "imaging_power_w", f"{context}.resource_model"
            ),
            slew_power_w=_require_float(resource_raw, "slew_power_w", f"{context}.resource_model"),
            sunlit_charge_power_w=_require_float(
                resource_raw, "sunlit_charge_power_w", f"{context}.resource_model"
            ),
        )
        if resource.battery_capacity_wh <= 0:
            raise ValueError(f"{context}.resource_model.battery_capacity_wh must be > 0")
        if resource.initial_battery_wh < -NUMERICAL_EPS or (
            resource.initial_battery_wh > resource.battery_capacity_wh + NUMERICAL_EPS
        ):
            raise ValueError(
                f"{context}.resource_model.initial_battery_wh must lie within [0, battery_capacity_wh]"
            )
        for field_name, value in (
            ("max_slew_velocity_deg_per_s", attitude.max_slew_velocity_deg_per_s),
            ("max_slew_acceleration_deg_per_s2", attitude.max_slew_acceleration_deg_per_s2),
            ("settling_time_s", attitude.settling_time_s),
            ("max_off_nadir_deg", attitude.max_off_nadir_deg),
            ("idle_power_w", resource.idle_power_w),
            ("imaging_power_w", resource.imaging_power_w),
            ("slew_power_w", resource.slew_power_w),
            ("sunlit_charge_power_w", resource.sunlit_charge_power_w),
        ):
            _validate_non_negative(value, field_name=f"{context}.{field_name}")
        satellites[sat_id] = SatelliteDef(
            satellite_id=sat_id,
            norad_catalog_id=_require_int(sat_raw, "norad_catalog_id", context),
            tle_line1=tle_line1,
            tle_line2=tle_line2,
            sensor=sensor,
            attitude_model=attitude,
            resource_model=resource,
        )

    tasks: dict[str, TaskDef] = {}
    for index, payload in enumerate(tasks_raw):
        context = f"tasks.yaml.tasks[{index}]"
        task_raw = _require_mapping(payload, context)
        task_id = _require_str(task_raw, "task_id", context)
        if task_id in tasks:
            raise ValueError(f"Duplicate task_id: {task_id}")
        release_time = _parse_iso_utc(
            _require_str(task_raw, "release_time", context),
            field_name=f"{context}.release_time",
        )
        due_time = _parse_iso_utc(
            _require_str(task_raw, "due_time", context),
            field_name=f"{context}.due_time",
        )
        required_duration_s = _require_int(task_raw, "required_duration_s", context)
        weight_value = task_raw.get("weight", 1.0)
        if not isinstance(weight_value, (int, float)):
            raise ValueError(f"{context}.weight must be numeric")
        weight = float(weight_value)
        if release_time < mission.horizon_start or release_time > mission.horizon_end:
            raise ValueError(f"{context}.release_time must lie inside the mission horizon")
        if due_time < mission.horizon_start or due_time > mission.horizon_end:
            raise ValueError(f"{context}.due_time must lie inside the mission horizon")
        if due_time <= release_time:
            raise ValueError(f"{context}.due_time must be after release_time")
        if required_duration_s <= 0:
            raise ValueError(f"{context}.required_duration_s must be > 0")
        if weight <= 0.0:
            raise ValueError(f"{context}.weight must be > 0")
        for field_name, seconds in (
            (f"{context}.release_time", (release_time - mission.horizon_start).total_seconds()),
            (f"{context}.due_time", (due_time - mission.horizon_start).total_seconds()),
            (f"{context}.required_duration_s", float(required_duration_s)),
        ):
            if not _is_aligned(seconds, mission.action_time_step_s):
                raise ValueError(
                    f"{field_name} must align to the {mission.action_time_step_s}s action grid"
                )
        if required_duration_s > int((due_time - release_time).total_seconds()):
            raise ValueError(f"{context}.required_duration_s exceeds the task window length")
        sensor_type = _require_str(task_raw, "required_sensor_type", context)
        if sensor_type not in {"visible", "infrared"}:
            raise ValueError(
                f"{context}.required_sensor_type must be 'visible' or 'infrared'"
            )
        tasks[task_id] = TaskDef(
            task_id=task_id,
            name=_require_str(task_raw, "name", context),
            latitude_deg=_require_float(task_raw, "latitude_deg", context),
            longitude_deg=_require_float(task_raw, "longitude_deg", context),
            altitude_m=_require_float(task_raw, "altitude_m", context),
            release_time=release_time,
            due_time=due_time,
            required_duration_s=required_duration_s,
            required_sensor_type=sensor_type,
            weight=weight,
            target_ecef_m=brahe.position_geodetic_to_ecef(
                [
                    _require_float(task_raw, "longitude_deg", context),
                    _require_float(task_raw, "latitude_deg", context),
                    _require_float(task_raw, "altitude_m", context),
                ],
                brahe.AngleFormat.DEGREES,
            ),
        )

    return AeosspCase(
        case_dir=case_path,
        mission=mission,
        satellites=satellites,
        tasks=tasks,
    )


def load_solution(solution_path: str | Path) -> AeosspSolution:
    path = Path(solution_path).resolve()
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("solution.json must be a JSON object")
    actions_raw = payload.get("actions", [])
    if not isinstance(actions_raw, list):
        raise ValueError("solution.json.actions must be a list")
    actions: list[ObservationAction] = []
    for index, payload in enumerate(actions_raw):
        context = f"solution.json.actions[{index}]"
        action_raw = _require_mapping(payload, context)
        action_type = _require_str(action_raw, "type", context)
        if action_type != "observation":
            raise ValueError(f"{context}.type {action_type!r} is unsupported")
        actions.append(
            ObservationAction(
                satellite_id=_require_str(action_raw, "satellite_id", context),
                task_id=_require_str(action_raw, "task_id", context),
                start_time=_parse_iso_utc(
                    _require_str(action_raw, "start_time", context),
                    field_name=f"{context}.start_time",
                ),
                end_time=_parse_iso_utc(
                    _require_str(action_raw, "end_time", context),
                    field_name=f"{context}.end_time",
                ),
            )
        )
    return AeosspSolution(actions=actions)


# ===== from aab_verifier/engine.py (unchanged) =====
"""Core verification logic for the aeossp_standard benchmark."""


from collections import defaultdict
from datetime import UTC, datetime, timedelta
import math
from pathlib import Path
from typing import Any

import brahe
import numpy as np



_BRAHE_EOP_INITIALIZED = False


class _PropagationContext:
    def __init__(self, case: AeosspCase):
        self.case = case
        step_s = float(min(case.mission.action_time_step_s, case.mission.geometry_sample_step_s))
        self.propagators = {
            sat_id: brahe.SGPPropagator.from_tle(sat.tle_line1, sat.tle_line2, step_s)
            for sat_id, sat in case.satellites.items()
        }
        self._eci_cache: dict[tuple[str, datetime], np.ndarray] = {}
        self._ecef_cache: dict[tuple[str, datetime], np.ndarray] = {}

    def state_eci(self, satellite_id: str, instant: datetime) -> np.ndarray:
        key = (satellite_id, instant.astimezone(UTC))
        state = self._eci_cache.get(key)
        if state is None:
            epoch = _datetime_to_epoch(key[1])
            state = np.asarray(self.propagators[satellite_id].state_eci(epoch), dtype=float).reshape(6)
            self._eci_cache[key] = state
        return state

    def state_ecef(self, satellite_id: str, instant: datetime) -> np.ndarray:
        key = (satellite_id, instant.astimezone(UTC))
        state = self._ecef_cache.get(key)
        if state is None:
            epoch = _datetime_to_epoch(key[1])
            state = np.asarray(self.propagators[satellite_id].state_ecef(epoch), dtype=float).reshape(6)
            self._ecef_cache[key] = state
        return state


def _ensure_brahe_ready() -> None:
    global _BRAHE_EOP_INITIALIZED
    if _BRAHE_EOP_INITIALIZED:
        return
    brahe.set_global_eop_provider_from_static_provider(
        brahe.StaticEOPProvider.from_zero()
    )
    _BRAHE_EOP_INITIALIZED = True


def _datetime_to_epoch(value: datetime) -> brahe.Epoch:
    value = value.astimezone(UTC)
    second = float(value.second) + (value.microsecond / 1_000_000.0)
    return brahe.Epoch.from_datetime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        second,
        0.0,
        brahe.TimeSystem.UTC,
    )


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _default_metrics() -> dict[str, Any]:
    return {"CR": 0.0, "WCR": 0.0, "TAT": None, "PC": 0.0}


def _invalid_result(
    violations: list[str], diagnostics: dict[str, Any] | None = None
) -> VerificationResult:
    return VerificationResult(
        valid=False,
        metrics=_default_metrics(),
        violations=violations,
        diagnostics=diagnostics or {},
    )


def _is_aligned(seconds: float, step_s: int) -> bool:
    return abs((seconds / step_s) - round(seconds / step_s)) <= 1.0e-9


def _action_sample_times(
    mission: Mission,
    start_time: datetime,
    end_time: datetime,
) -> list[datetime]:
    if end_time <= start_time:
        return [start_time]
    points = [start_time]
    step_s = mission.geometry_sample_step_s
    start_offset_s = int(round((start_time - mission.horizon_start).total_seconds()))
    end_offset_s = int(round((end_time - mission.horizon_start).total_seconds()))
    next_grid_offset_s = ((start_offset_s // step_s) + 1) * step_s
    while next_grid_offset_s < end_offset_s:
        points.append(mission.horizon_start + timedelta(seconds=next_grid_offset_s))
        next_grid_offset_s += step_s
    if points[-1] != end_time:
        points.append(end_time)
    return points


def _angle_between_deg(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    norm_a = float(np.linalg.norm(vector_a))
    norm_b = float(np.linalg.norm(vector_b))
    if norm_a <= NUMERICAL_EPS or norm_b <= NUMERICAL_EPS:
        return 0.0
    cosine = float(np.dot(vector_a, vector_b) / (norm_a * norm_b))
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def _off_nadir_deg(satellite_position_ecef_m: np.ndarray, target_ecef_m: np.ndarray) -> float:
    return _angle_between_deg(
        -satellite_position_ecef_m,
        target_ecef_m - satellite_position_ecef_m,
    )


def _target_visible(
    satellite_position_ecef_m: np.ndarray,
    target_ecef_m: np.ndarray,
) -> bool:
    target_norm = float(np.linalg.norm(target_ecef_m))
    if target_norm <= NUMERICAL_EPS:
        return False
    target_normal = target_ecef_m / target_norm
    return float(np.dot(satellite_position_ecef_m - target_ecef_m, target_normal)) > 0.0


def _target_vector_eci(
    task: TaskDef,
    propagation: _PropagationContext,
    satellite_id: str,
    instant: datetime,
) -> np.ndarray:
    epoch = _datetime_to_epoch(instant)
    target_eci = np.asarray(
        brahe.position_ecef_to_eci(epoch, np.asarray(task.target_ecef_m, dtype=float)),
        dtype=float,
    ).reshape(3)
    sat_state_eci = propagation.state_eci(satellite_id, instant)
    return target_eci - sat_state_eci[:3]


def _is_sunlit(position_eci_m: np.ndarray, epoch: brahe.Epoch) -> bool:
    sun_position = np.asarray(brahe.sun_position(epoch), dtype=float)
    sun_hat = sun_position / np.linalg.norm(sun_position)
    projection = float(np.dot(position_eci_m, sun_hat))
    perpendicular = np.linalg.norm(position_eci_m - (projection * sun_hat))
    return not (projection < 0.0 and perpendicular < brahe.R_EARTH)


def _slew_time_s(
    delta_angle_deg: float,
    max_velocity_deg_per_s: float,
    max_acceleration_deg_per_s2: float,
) -> float:
    delta_angle_deg = max(0.0, delta_angle_deg)
    if delta_angle_deg <= NUMERICAL_EPS:
        return 0.0
    if max_velocity_deg_per_s <= 0.0 or max_acceleration_deg_per_s2 <= 0.0:
        return math.inf
    ramp_time = max_velocity_deg_per_s / max_acceleration_deg_per_s2
    triangular_threshold = (
        max_velocity_deg_per_s * max_velocity_deg_per_s / max_acceleration_deg_per_s2
    )
    if delta_angle_deg <= triangular_threshold:
        return 2.0 * math.sqrt(delta_angle_deg / max_acceleration_deg_per_s2)
    cruise_angle = delta_angle_deg - triangular_threshold
    return (2.0 * ramp_time) + (cruise_angle / max_velocity_deg_per_s)


def _make_failure(
    *,
    action_index: int,
    satellite_id: str,
    task_id: str,
    reason: str,
    stage: str,
    time: datetime | None = None,
) -> ActionFailure:
    return ActionFailure(
        action_index=action_index,
        satellite_id=satellite_id,
        task_id=task_id,
        reason=reason,
        stage=stage,
        time=time.astimezone(UTC) if time is not None else None,
    )


def _validate_action_structure(
    case: AeosspCase,
    solution: AeosspSolution,
) -> tuple[list[ValidatedAction], list[ActionFailure], list[str]]:
    validated: list[ValidatedAction] = []
    failures: list[ActionFailure] = []
    violations: list[str] = []
    for index, action in enumerate(solution.actions):
        prefix = f"actions[{index}]"
        if action.satellite_id not in case.satellites:
            failures.append(
                _make_failure(
                    action_index=index,
                    satellite_id=action.satellite_id,
                    task_id=action.task_id,
                    reason="unknown satellite_id",
                    stage="structure",
                    time=action.start_time,
                )
            )
            violations.append(f"{prefix}: unknown satellite_id {action.satellite_id!r}")
            continue
        if action.task_id not in case.tasks:
            failures.append(
                _make_failure(
                    action_index=index,
                    satellite_id=action.satellite_id,
                    task_id=action.task_id,
                    reason="unknown task_id",
                    stage="structure",
                    time=action.start_time,
                )
            )
            violations.append(f"{prefix}: unknown task_id {action.task_id!r}")
            continue
        task = case.tasks[action.task_id]
        if action.end_time <= action.start_time:
            reason = "end_time must be after start_time"
            failures.append(
                _make_failure(
                    action_index=index,
                    satellite_id=action.satellite_id,
                    task_id=action.task_id,
                    reason=reason,
                    stage="structure",
                    time=action.start_time,
                )
            )
            violations.append(f"{prefix}: {reason}")
            continue
        if action.start_time < case.mission.horizon_start or action.end_time > case.mission.horizon_end:
            reason = "action lies outside the mission horizon"
            failures.append(
                _make_failure(
                    action_index=index,
                    satellite_id=action.satellite_id,
                    task_id=action.task_id,
                    reason=reason,
                    stage="structure",
                    time=action.start_time,
                )
            )
            violations.append(f"{prefix}: {reason}")
            continue
        misaligned = False
        for field_name, instant in (("start_time", action.start_time), ("end_time", action.end_time)):
            seconds = (instant - case.mission.horizon_start).total_seconds()
            if not _is_aligned(seconds, case.mission.action_time_step_s):
                reason = f"{field_name} must align to the {case.mission.action_time_step_s}s action grid"
                failures.append(
                    _make_failure(
                        action_index=index,
                        satellite_id=action.satellite_id,
                        task_id=action.task_id,
                        reason=reason,
                        stage="structure",
                        time=instant,
                    )
                )
                violations.append(f"{prefix}: {reason}")
                misaligned = True
                break
        if misaligned:
            continue
        if action.start_time < task.release_time or action.end_time > task.due_time:
            reason = "action lies outside the task window"
            failures.append(
                _make_failure(
                    action_index=index,
                    satellite_id=action.satellite_id,
                    task_id=action.task_id,
                    reason=reason,
                    stage="structure",
                    time=action.start_time,
                )
            )
            violations.append(f"{prefix}: {reason}")
            continue
        if action.duration_s != task.required_duration_s:
            reason = (
                f"action duration must equal required_duration_s "
                f"({task.required_duration_s}s)"
            )
            failures.append(
                _make_failure(
                    action_index=index,
                    satellite_id=action.satellite_id,
                    task_id=action.task_id,
                    reason=reason,
                    stage="structure",
                    time=action.start_time,
                )
            )
            violations.append(f"{prefix}: {reason}")
            continue
        satellite = case.satellites[action.satellite_id]
        if satellite.sensor.sensor_type != task.required_sensor_type:
            reason = "satellite sensor_type does not match task required_sensor_type"
            failures.append(
                _make_failure(
                    action_index=index,
                    satellite_id=action.satellite_id,
                    task_id=action.task_id,
                    reason=reason,
                    stage="structure",
                    time=action.start_time,
                )
            )
            violations.append(f"{prefix}: {reason}")
            continue
        validated.append(
            ValidatedAction(
                action_index=index,
                satellite_id=action.satellite_id,
                task_id=action.task_id,
                start_time=action.start_time,
                end_time=action.end_time,
            )
        )
    return validated, failures, violations


def _validate_observation_geometry(
    case: AeosspCase,
    propagation: _PropagationContext,
    validated_actions: list[ValidatedAction],
    failures: list[ActionFailure],
    violations: list[str],
) -> list[ValidatedAction]:
    accepted: list[ValidatedAction] = []
    for item in validated_actions:
        satellite = case.satellites[item.satellite_id]
        task = case.tasks[item.task_id]
        sample_times = _action_sample_times(
            case.mission,
            item.start_time,
            item.end_time,
        )
        bad_reason: str | None = None
        bad_time: datetime | None = None
        for sample_time in sample_times:
            state_ecef = propagation.state_ecef(item.satellite_id, sample_time)
            sat_pos_ecef = state_ecef[:3]
            if not _target_visible(sat_pos_ecef, np.asarray(task.target_ecef_m, dtype=float)):
                bad_reason = "target is not continuously visible"
                bad_time = sample_time
                break
            off_nadir_deg = _off_nadir_deg(sat_pos_ecef, np.asarray(task.target_ecef_m, dtype=float))
            if off_nadir_deg > satellite.attitude_model.max_off_nadir_deg + 1.0e-6:
                bad_reason = "required pointing exceeds max_off_nadir_deg"
                bad_time = sample_time
                break
        if bad_reason is not None:
            failure_text = f"{bad_reason} at {_iso_z(bad_time)}" if bad_time is not None else bad_reason
            failures.append(
                _make_failure(
                    action_index=item.action_index,
                    satellite_id=item.satellite_id,
                    task_id=item.task_id,
                    reason=failure_text,
                    stage="geometry",
                    time=bad_time,
                )
            )
            violations.append(f"actions[{item.action_index}]: {failure_text}")
            continue
        accepted.append(item)
    return accepted


def _validate_slew_and_build_maneuver_windows(
    case: AeosspCase,
    propagation: _PropagationContext,
    actions_by_satellite: dict[str, list[ValidatedAction]],
    failures: list[ActionFailure],
    violations: list[str],
) -> tuple[dict[str, list[ValidatedAction]], dict[str, list[ManeuverWindow]]]:
    accepted_actions_by_satellite: dict[str, list[ValidatedAction]] = defaultdict(list)
    maneuver_windows: dict[str, list[ManeuverWindow]] = defaultdict(list)
    for satellite_id, actions in actions_by_satellite.items():
        satellite = case.satellites[satellite_id]
        actions.sort(key=lambda item: (item.start_time, item.end_time, item.action_index))
        previous: ValidatedAction | None = None
        for current in actions:
            if previous is not None and previous.end_time > current.start_time:
                reason = "observation actions overlap on the same satellite"
                failures.append(
                    _make_failure(
                        action_index=current.action_index,
                        satellite_id=satellite_id,
                        task_id=current.task_id,
                        reason=reason,
                        stage="slew",
                        time=current.start_time,
                    )
                )
                violations.append(f"actions[{current.action_index}]: {reason}")
                continue
            current_task = case.tasks[current.task_id]
            current_start_vec = _target_vector_eci(
                current_task, propagation, satellite_id, current.start_time
            )
            if previous is None:
                sat_state_eci = propagation.state_eci(satellite_id, current.start_time)
                from_vector = -sat_state_eci[:3]
                available_gap_s = (
                    current.start_time - case.mission.horizon_start
                ).total_seconds()
                from_task_id = None
                from_action_index = None
            else:
                previous_task = case.tasks[previous.task_id]
                from_vector = _target_vector_eci(
                    previous_task, propagation, satellite_id, previous.end_time
                )
                available_gap_s = (
                    current.start_time - previous.end_time
                ).total_seconds()
                from_task_id = previous.task_id
                from_action_index = previous.action_index
            slew_angle_deg = _angle_between_deg(from_vector, current_start_vec)
            slew_time_s = _slew_time_s(
                slew_angle_deg,
                satellite.attitude_model.max_slew_velocity_deg_per_s,
                satellite.attitude_model.max_slew_acceleration_deg_per_s2,
            )
            required_gap_s = slew_time_s + satellite.attitude_model.settling_time_s
            if available_gap_s + NUMERICAL_EPS < required_gap_s:
                reason = (
                    f"insufficient slew/settle time before observation "
                    f"(need {required_gap_s:.3f}s, have {available_gap_s:.3f}s)"
                )
                failures.append(
                    _make_failure(
                        action_index=current.action_index,
                        satellite_id=satellite_id,
                        task_id=current.task_id,
                        reason=reason,
                        stage="slew",
                        time=current.start_time,
                    )
                )
                violations.append(f"actions[{current.action_index}]: {reason}")
                continue
            if required_gap_s > NUMERICAL_EPS:
                window_start = current.start_time - timedelta(seconds=required_gap_s)
                maneuver_windows[satellite_id].append(
                    ManeuverWindow(
                        action_index=current.action_index,
                        satellite_id=satellite_id,
                        start_time=window_start,
                        end_time=current.start_time,
                        required_gap_s=required_gap_s,
                        slew_angle_deg=slew_angle_deg,
                        from_action_index=from_action_index,
                        from_task_id=from_task_id,
                        to_task_id=current.task_id,
                    )
                )
            accepted_actions_by_satellite[satellite_id].append(current)
            previous = current
    return accepted_actions_by_satellite, maneuver_windows


def _interval_contains(instant: datetime, start: datetime, end: datetime) -> bool:
    return start <= instant < end


def _resource_time_points(
    mission: Mission,
    actions: list[ValidatedAction],
    maneuver_windows: list[ManeuverWindow],
) -> list[datetime]:
    points: set[datetime] = {mission.horizon_start, mission.horizon_end}
    current = mission.horizon_start
    delta = timedelta(seconds=mission.resource_sample_step_s)
    while current < mission.horizon_end:
        points.add(current)
        current = min(current + delta, mission.horizon_end)
    points.add(mission.horizon_end)
    for item in actions:
        points.add(item.start_time)
        points.add(item.end_time)
    for window in maneuver_windows:
        points.add(window.start_time)
        points.add(window.end_time)
    return sorted(points)


def _segment_mode(
    active_observation: ValidatedAction | None,
    active_maneuver: ManeuverWindow | None,
) -> str:
    if active_observation is not None and active_maneuver is not None:
        return "observation+slew"
    if active_observation is not None:
        return "observation"
    if active_maneuver is not None:
        return "slew"
    return "idle"


def _simulate_battery_and_power(
    case: AeosspCase,
    propagation: _PropagationContext,
    actions_by_satellite: dict[str, list[ValidatedAction]],
    maneuver_windows: dict[str, list[ManeuverWindow]],
    failures: list[ActionFailure],
    violations: list[str],
) -> tuple[float, dict[str, Any], dict[str, tuple[BatteryTraceSegment, ...]]]:
    total_pc_wh = 0.0
    summaries: dict[str, Any] = {}
    traces: dict[str, tuple[BatteryTraceSegment, ...]] = {}
    for satellite_id, satellite in case.satellites.items():
        actions = sorted(
            actions_by_satellite.get(satellite_id, []),
            key=lambda item: (item.start_time, item.end_time, item.action_index),
        )
        windows = maneuver_windows.get(satellite_id, [])
        time_points = _resource_time_points(case.mission, actions, windows)
        battery_wh = satellite.resource_model.initial_battery_wh
        min_battery_wh = battery_wh
        min_battery_time = case.mission.horizon_start
        gross_consumption_wh = 0.0
        total_charge_wh = 0.0
        total_imaging_time_s = 0.0
        total_slew_time_s = 0.0
        failed = False
        trace_segments: list[BatteryTraceSegment] = []
        for start_time, end_time in zip(time_points, time_points[1:]):
            duration_s = (end_time - start_time).total_seconds()
            if duration_s <= 0.0:
                continue
            midpoint = start_time + ((end_time - start_time) / 2)
            active_observation = next(
                (
                    item
                    for item in actions
                    if _interval_contains(midpoint, item.start_time, item.end_time)
                ),
                None,
            )
            active_maneuver = next(
                (
                    window
                    for window in windows
                    if _interval_contains(midpoint, window.start_time, window.end_time)
                ),
                None,
            )
            load_power_w = satellite.resource_model.idle_power_w
            if active_observation is not None:
                load_power_w += satellite.resource_model.imaging_power_w
                total_imaging_time_s += duration_s
            if active_maneuver is not None:
                load_power_w += satellite.resource_model.slew_power_w
                total_slew_time_s += duration_s
            epoch = _datetime_to_epoch(midpoint)
            state_eci = propagation.state_eci(satellite_id, midpoint)
            charge_power_w = (
                satellite.resource_model.sunlit_charge_power_w
                if _is_sunlit(state_eci[:3], epoch)
                else 0.0
            )
            battery_start_wh = battery_wh
            gross_consumption_wh += (load_power_w * duration_s) / 3600.0
            total_charge_wh += (charge_power_w * duration_s) / 3600.0
            battery_wh += ((charge_power_w - load_power_w) * duration_s) / 3600.0
            if battery_wh < -NUMERICAL_EPS:
                reason = f"battery depletes below zero around {_iso_z(midpoint)}"
                failing_index = active_observation.action_index if active_observation else -1
                failing_task = active_observation.task_id if active_observation else ""
                failures.append(
                    _make_failure(
                        action_index=failing_index,
                        satellite_id=satellite_id,
                        task_id=failing_task,
                        reason=reason,
                        stage="battery",
                        time=midpoint,
                    )
                )
                violations.append(f"Satellite {satellite_id}: {reason}")
                failed = True
                battery_end_wh = battery_wh
            else:
                battery_wh = min(satellite.resource_model.battery_capacity_wh, battery_wh)
                battery_end_wh = battery_wh
                if battery_wh < min_battery_wh:
                    min_battery_wh = battery_wh
                    min_battery_time = end_time
            trace_segments.append(
                BatteryTraceSegment(
                    satellite_id=satellite_id,
                    start_time=start_time,
                    end_time=end_time,
                    battery_start_wh=battery_start_wh,
                    battery_end_wh=battery_end_wh,
                    load_power_w=load_power_w,
                    charge_power_w=charge_power_w,
                    mode=_segment_mode(active_observation, active_maneuver),
                    active_action_index=active_observation.action_index if active_observation else None,
                    active_task_id=active_observation.task_id if active_observation else None,
                    active_maneuver_to_action_index=active_maneuver.action_index if active_maneuver else None,
                )
            )
            if failed:
                break
        summaries[satellite_id] = {
            "initial_battery_wh": satellite.resource_model.initial_battery_wh,
            "minimum_battery_wh": min_battery_wh,
            "minimum_battery_time": _iso_z(min_battery_time),
            "final_battery_wh": battery_wh,
            "gross_consumption_wh": gross_consumption_wh,
            "total_charge_wh": total_charge_wh,
            "total_imaging_time_s": total_imaging_time_s,
            "total_slew_time_s": total_slew_time_s,
            "failed": failed,
        }
        traces[satellite_id] = tuple(trace_segments)
        if not failed:
            total_pc_wh += gross_consumption_wh
    return total_pc_wh, summaries, traces


def _compute_task_outcomes(
    case: AeosspCase,
    validated_actions: list[ValidatedAction],
) -> dict[str, TaskOutcome]:
    completed_by_task: dict[str, ValidatedAction] = {}
    for item in sorted(
        validated_actions,
        key=lambda item: (item.end_time, item.start_time, item.action_index),
    ):
        current = completed_by_task.get(item.task_id)
        if current is None or item.end_time < current.end_time:
            completed_by_task[item.task_id] = item
    outcomes: dict[str, TaskOutcome] = {}
    for task_id, task in case.tasks.items():
        completion = completed_by_task.get(task_id)
        outcomes[task_id] = TaskOutcome(
            task_id=task_id,
            completed=completion is not None,
            completion_time=completion.end_time if completion is not None else None,
            completed_by_action_index=completion.action_index if completion is not None else None,
            weight=task.weight,
        )
    return outcomes


def _compute_metrics(
    case: AeosspCase,
    task_outcomes: dict[str, TaskOutcome],
    total_pc_wh: float,
) -> dict[str, Any]:
    total_tasks = len(case.tasks)
    completed = [outcome for outcome in task_outcomes.values() if outcome.completed]
    total_weight = sum(task.weight for task in case.tasks.values())
    completed_weight = sum(outcome.weight for outcome in completed)
    tat_values_s = [
        (
            outcome.completion_time - case.tasks[outcome.task_id].release_time
        ).total_seconds()
        for outcome in completed
        if outcome.completion_time is not None
    ]
    return {
        "CR": len(completed) / total_tasks if total_tasks else 0.0,
        "WCR": completed_weight / total_weight if total_weight > 0.0 else 0.0,
        "TAT": (sum(tat_values_s) / len(tat_values_s)) if tat_values_s else None,
        "PC": total_pc_wh,
    }


def _build_timeline_events(
    validated_actions: list[ValidatedAction],
    maneuver_windows: tuple[ManeuverWindow, ...],
    failures: list[ActionFailure],
) -> tuple[TimelineEvent, ...]:
    events: list[TimelineEvent] = []
    for action in validated_actions:
        events.append(
            TimelineEvent(
                time=action.start_time,
                satellite_id=action.satellite_id,
                kind="action_start",
                action_index=action.action_index,
                task_id=action.task_id,
            )
        )
        events.append(
            TimelineEvent(
                time=action.end_time,
                satellite_id=action.satellite_id,
                kind="action_end",
                action_index=action.action_index,
                task_id=action.task_id,
            )
        )
    for window in maneuver_windows:
        events.append(
            TimelineEvent(
                time=window.start_time,
                satellite_id=window.satellite_id,
                kind="maneuver_start",
                action_index=window.action_index,
                task_id=window.to_task_id,
            )
        )
        events.append(
            TimelineEvent(
                time=window.end_time,
                satellite_id=window.satellite_id,
                kind="maneuver_end",
                action_index=window.action_index,
                task_id=window.to_task_id,
            )
        )
    for failure in failures:
        if failure.time is None:
            continue
        events.append(
            TimelineEvent(
                time=failure.time,
                satellite_id=failure.satellite_id,
                kind="failure",
                action_index=failure.action_index if failure.action_index >= 0 else None,
                task_id=failure.task_id or None,
                detail=failure.reason,
            )
        )
    events.sort(key=lambda item: (item.time, item.satellite_id, item.kind, item.action_index or -1))
    return tuple(events)


def _build_snapshot_candidates(
    validated_actions: list[ValidatedAction],
    failures: list[ActionFailure],
    resource_summary: dict[str, Any],
) -> tuple[datetime, ...]:
    candidates: list[datetime] = []
    for action in validated_actions:
        candidates.extend((action.start_time, action.end_time))
    for failure in failures:
        if failure.time is not None:
            candidates.append(failure.time)
    for summary in resource_summary.values():
        minimum_battery_time = summary.get("minimum_battery_time")
        if isinstance(minimum_battery_time, str):
            candidates.append(datetime.fromisoformat(minimum_battery_time.replace("Z", "+00:00")).astimezone(UTC))
    unique = sorted({candidate.astimezone(UTC) for candidate in candidates})
    return tuple(unique)


def _build_diagnostics(
    task_outcomes: dict[str, TaskOutcome],
    failures: list[ActionFailure],
    maneuver_windows: tuple[ManeuverWindow, ...],
    resource_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "action_failures": [failure.as_dict() for failure in failures],
        "maneuver_windows": [window.as_dict() for window in maneuver_windows],
        "per_task": {
            task_id: outcome.as_dict()
            for task_id, outcome in task_outcomes.items()
        },
        "per_satellite_resource_summary": resource_summary,
    }


def analyze(case: AeosspCase, solution: AeosspSolution) -> SolutionAnalysis:
    _ensure_brahe_ready()
    propagation = _PropagationContext(case)

    validated_actions, failures, violations = _validate_action_structure(case, solution)
    validated_actions = _validate_observation_geometry(
        case, propagation, validated_actions, failures, violations
    )

    actions_by_satellite: dict[str, list[ValidatedAction]] = defaultdict(list)
    for item in validated_actions:
        actions_by_satellite[item.satellite_id].append(item)

    accepted_actions_by_satellite, maneuver_windows_by_satellite = _validate_slew_and_build_maneuver_windows(
        case, propagation, actions_by_satellite, failures, violations
    )
    accepted_actions = [
        item
        for satellite_id in sorted(accepted_actions_by_satellite)
        for item in accepted_actions_by_satellite[satellite_id]
    ]
    maneuver_windows = tuple(
        window
        for satellite_id in sorted(maneuver_windows_by_satellite)
        for window in maneuver_windows_by_satellite[satellite_id]
    )

    total_pc_wh = 0.0
    resource_summary: dict[str, Any] = {}
    battery_traces: dict[str, tuple[BatteryTraceSegment, ...]] = {
        sat_id: tuple() for sat_id in case.satellites
    }
    total_pc_wh, resource_summary, battery_traces = _simulate_battery_and_power(
        case,
        propagation,
        accepted_actions_by_satellite,
        maneuver_windows_by_satellite,
        failures,
        violations,
    )

    task_outcomes = _compute_task_outcomes(case, accepted_actions)
    diagnostics = _build_diagnostics(task_outcomes, failures, maneuver_windows, resource_summary)
    timeline_events = _build_timeline_events(accepted_actions, maneuver_windows, failures)
    snapshot_candidates = _build_snapshot_candidates(accepted_actions, failures, resource_summary)

    if violations:
        result = VerificationResult(
            valid=False,
            metrics=_default_metrics(),
            violations=violations,
            diagnostics=diagnostics,
        )
    else:
        result = VerificationResult(
            valid=True,
            metrics=_compute_metrics(case, task_outcomes, total_pc_wh),
            violations=[],
            diagnostics=diagnostics,
        )

    return SolutionAnalysis(
        case=case,
        solution=solution,
        result=result,
        validated_actions=tuple(
            sorted(accepted_actions, key=lambda item: (item.start_time, item.end_time, item.action_index))
        ),
        action_failures=tuple(failures),
        maneuver_windows=maneuver_windows,
        task_outcomes=task_outcomes,
        battery_traces=battery_traces,
        per_satellite_resource_summary=resource_summary,
        timeline_events=timeline_events,
        snapshot_candidates=snapshot_candidates,
    )


def analyze_solution(case_dir: str | Path, solution_path: str | Path) -> SolutionAnalysis:
    case = load_case(case_dir)
    solution = load_solution(solution_path)
    return analyze(case, solution)


def verify(case: AeosspCase, solution: AeosspSolution) -> VerificationResult:
    return analyze(case, solution).result


def verify_solution(case_dir: str | Path, solution_path: str | Path) -> VerificationResult:
    try:
        return analyze_solution(case_dir, solution_path).result
    except (FileNotFoundError, ValueError) as exc:
        return _invalid_result([str(exc)], diagnostics={})
