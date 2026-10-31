"""Frozen official AstroAgentBench revisit_constellation verifier, merged into one file (code unchanged)."""
from __future__ import annotations
# ===== from revisit_constellation/verifier/models.py (unchanged) =====
"""Shared data models for the revisit_constellation verifier."""


from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json

import numpy as np


DEFAULT_DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
ACTION_SAMPLE_STEP_SEC = 10.0
RESOURCE_STEP_SEC = 30.0
NUMERICAL_EPS = 1e-9


@dataclass(frozen=True)
class SensorModel:
    max_off_nadir_angle_deg: float
    max_range_m: float
    obs_discharge_rate_w: float


@dataclass(frozen=True)
class ResourceModel:
    battery_capacity_wh: float
    initial_battery_wh: float
    idle_discharge_rate_w: float
    sunlight_charge_rate_w: float


@dataclass(frozen=True)
class AttitudeModel:
    max_slew_velocity_deg_per_sec: float
    max_slew_acceleration_deg_per_sec2: float
    settling_time_sec: float
    maneuver_discharge_rate_w: float


@dataclass(frozen=True)
class SatelliteModel:
    model_name: str
    sensor: SensorModel
    resource_model: ResourceModel
    attitude_model: AttitudeModel
    min_altitude_m: float
    max_altitude_m: float


@dataclass(frozen=True)
class Target:
    target_id: str
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    expected_revisit_period_hours: float
    min_elevation_deg: float
    max_slant_range_m: float
    min_duration_sec: float
    ecef_position_m: np.ndarray = field(repr=False)


@dataclass(frozen=True)
class Instance:
    case_dir: Path
    assets_path: Path
    mission_path: Path
    horizon_start: datetime
    horizon_end: datetime
    satellite_model: SatelliteModel
    max_num_satellites: int
    targets: dict[str, Target]

    @property
    def horizon_duration_sec(self) -> float:
        return (self.horizon_end - self.horizon_start).total_seconds()


@dataclass(frozen=True)
class SatelliteDefinition:
    satellite_id: str
    state_eci_m_mps: np.ndarray = field(repr=False)


@dataclass(frozen=True)
class Action:
    action_type: str
    satellite_id: str
    start: datetime
    end: datetime
    target_id: str | None = None

    @property
    def duration_sec(self) -> float:
        return (self.end - self.start).total_seconds()


@dataclass(frozen=True)
class Solution:
    satellites: dict[str, SatelliteDefinition]
    actions: list[Action]


@dataclass(frozen=True)
class ObservationRecord:
    satellite_id: str
    target_id: str
    start: datetime
    end: datetime
    midpoint: datetime


@dataclass(frozen=True)
class ManeuverWindow:
    satellite_id: str
    start: datetime
    end: datetime


@dataclass
class VerificationResult:
    is_valid: bool
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "metrics": self.metrics,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def __str__(self) -> str:  # pragma: no cover - formatting helper
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

# ===== from revisit_constellation/verifier/io.py (unchanged) =====
"""Case and solution loading for the revisit_constellation verifier."""


from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json

import brahe
import numpy as np



def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_iso8601_utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"Expected ISO 8601 timestamp string, got {type(value).__name__}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include timezone information: {value!r}")
    return parsed.astimezone(UTC)


def _require_mapping(payload: Any, context: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{context} must be a JSON object")
    return payload


def _require_list(payload: Any, context: str) -> list[Any]:
    if not isinstance(payload, list):
        raise ValueError(f"{context} must be a JSON array")
    return payload


def _require_str(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def _require_float(mapping: dict[str, Any], key: str, context: str) -> float:
    value = mapping.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{context}.{key} must be numeric")
    return float(value)


def _require_int(mapping: dict[str, Any], key: str, context: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{context}.{key} must be an integer")
    return value


def _geodetic_to_ecef(longitude_deg: float, latitude_deg: float, altitude_m: float) -> np.ndarray:
    return np.asarray(
        brahe.position_geodetic_to_ecef(
            [longitude_deg, latitude_deg, altitude_m],
            brahe.AngleFormat.DEGREES,
        ),
        dtype=float,
    )


def _parse_target(payload: dict[str, Any], index: int) -> Target:
    context = f"mission.json.targets[{index}]"
    return Target(
        target_id=_require_str(payload, "id", context),
        name=_require_str(payload, "name", context),
        latitude_deg=_require_float(payload, "latitude_deg", context),
        longitude_deg=_require_float(payload, "longitude_deg", context),
        altitude_m=_require_float(payload, "altitude_m", context),
        expected_revisit_period_hours=_require_float(
            payload, "expected_revisit_period_hours", context
        ),
        min_elevation_deg=_require_float(payload, "min_elevation_deg", context),
        max_slant_range_m=_require_float(payload, "max_slant_range_m", context),
        min_duration_sec=_require_float(payload, "min_duration_sec", context),
        ecef_position_m=_geodetic_to_ecef(
            _require_float(payload, "longitude_deg", context),
            _require_float(payload, "latitude_deg", context),
            _require_float(payload, "altitude_m", context),
        ),
    )


def _parse_satellite_model(payload: dict[str, Any]) -> SatelliteModel:
    context = "assets.json.satellite_model"
    sensor_payload = _require_mapping(payload.get("sensor"), f"{context}.sensor")
    resource_payload = _require_mapping(
        payload.get("resource_model"), f"{context}.resource_model"
    )
    attitude_payload = _require_mapping(
        payload.get("attitude_model"), f"{context}.attitude_model"
    )

    return SatelliteModel(
        model_name=_require_str(payload, "model_name", context),
        sensor=SensorModel(
            max_off_nadir_angle_deg=_require_float(
                sensor_payload, "max_off_nadir_angle_deg", f"{context}.sensor"
            ),
            max_range_m=_require_float(
                sensor_payload, "max_range_m", f"{context}.sensor"
            ),
            obs_discharge_rate_w=_require_float(
                sensor_payload, "obs_discharge_rate_w", f"{context}.sensor"
            ),
        ),
        resource_model=ResourceModel(
            battery_capacity_wh=_require_float(
                resource_payload, "battery_capacity_wh", f"{context}.resource_model"
            ),
            initial_battery_wh=_require_float(
                resource_payload, "initial_battery_wh", f"{context}.resource_model"
            ),
            idle_discharge_rate_w=_require_float(
                resource_payload, "idle_discharge_rate_w", f"{context}.resource_model"
            ),
            sunlight_charge_rate_w=_require_float(
                resource_payload, "sunlight_charge_rate_w", f"{context}.resource_model"
            ),
        ),
        attitude_model=AttitudeModel(
            max_slew_velocity_deg_per_sec=_require_float(
                attitude_payload,
                "max_slew_velocity_deg_per_sec",
                f"{context}.attitude_model",
            ),
            max_slew_acceleration_deg_per_sec2=_require_float(
                attitude_payload,
                "max_slew_acceleration_deg_per_sec2",
                f"{context}.attitude_model",
            ),
            settling_time_sec=_require_float(
                attitude_payload, "settling_time_sec", f"{context}.attitude_model"
            ),
            maneuver_discharge_rate_w=_require_float(
                attitude_payload,
                "maneuver_discharge_rate_w",
                f"{context}.attitude_model",
            ),
        ),
        min_altitude_m=_require_float(payload, "min_altitude_m", context),
        max_altitude_m=_require_float(payload, "max_altitude_m", context),
    )


def load_case(case_dir: str | Path) -> Instance:
    case_path = Path(case_dir)
    assets_path = case_path / "assets.json"
    mission_path = case_path / "mission.json"

    if not case_path.exists():
        raise FileNotFoundError(f"Case directory not found: {case_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Missing case file: {assets_path}")
    if not mission_path.exists():
        raise FileNotFoundError(f"Missing case file: {mission_path}")

    assets_payload = _require_mapping(_load_json(assets_path), "assets.json")
    mission_payload = _require_mapping(_load_json(mission_path), "mission.json")

    satellite_model = _parse_satellite_model(
        _require_mapping(assets_payload.get("satellite_model"), "assets.json.satellite_model")
    )
    max_num_satellites = _require_int(assets_payload, "max_num_satellites", "assets.json")
    if max_num_satellites < 0:
        raise ValueError("assets.json.max_num_satellites must be non-negative")

    targets_list = _require_list(mission_payload.get("targets"), "mission.json.targets")

    targets = {
        target.target_id: target
        for target in (
            _parse_target(_require_mapping(item, f"mission.json.targets[{index}]"), index)
            for index, item in enumerate(targets_list)
        )
    }
    if len(targets) != len(targets_list):
        raise ValueError("Target IDs must be unique within a case")

    horizon_start = _parse_iso8601_utc(
        _require_str(mission_payload, "horizon_start", "mission.json")
    )
    horizon_end = _parse_iso8601_utc(
        _require_str(mission_payload, "horizon_end", "mission.json")
    )
    if horizon_end <= horizon_start:
        raise ValueError("mission.json horizon_end must be after horizon_start")

    return Instance(
        case_dir=case_path,
        assets_path=assets_path,
        mission_path=mission_path,
        horizon_start=horizon_start,
        horizon_end=horizon_end,
        satellite_model=satellite_model,
        max_num_satellites=max_num_satellites,
        targets=targets,
    )


def _parse_satellite_definition(payload: dict[str, Any], index: int) -> SatelliteDefinition:
    context = f"solution.json.satellites[{index}]"
    return SatelliteDefinition(
        satellite_id=_require_str(payload, "satellite_id", context),
        state_eci_m_mps=np.asarray(
            [
                _require_float(payload, "x_m", context),
                _require_float(payload, "y_m", context),
                _require_float(payload, "z_m", context),
                _require_float(payload, "vx_m_s", context),
                _require_float(payload, "vy_m_s", context),
                _require_float(payload, "vz_m_s", context),
            ],
            dtype=float,
        ),
    )


def _parse_action(payload: dict[str, Any], index: int) -> Action:
    context = f"solution.json.actions[{index}]"
    action_type = _require_str(payload, "action_type", context)
    satellite_id = _require_str(payload, "satellite_id", context)
    start = _parse_iso8601_utc(_require_str(payload, "start", context))
    end = _parse_iso8601_utc(_require_str(payload, "end", context))
    target_id = payload.get("target_id")

    if target_id is not None and not isinstance(target_id, str):
        raise ValueError(f"{context}.target_id must be a string when present")

    return Action(
        action_type=action_type,
        satellite_id=satellite_id,
        start=start,
        end=end,
        target_id=target_id,
    )


def load_solution(solution_path: str | Path) -> Solution:
    payload = _require_mapping(_load_json(Path(solution_path)), "solution.json")
    satellites_payload = _require_list(payload.get("satellites"), "solution.json.satellites")
    actions_payload = _require_list(payload.get("actions"), "solution.json.actions")

    satellites: dict[str, SatelliteDefinition] = {}
    for index, item in enumerate(satellites_payload):
        satellite = _parse_satellite_definition(
            _require_mapping(item, f"solution.json.satellites[{index}]"), index
        )
        if satellite.satellite_id in satellites:
            raise ValueError(f"Duplicate satellite_id in solution: {satellite.satellite_id}")
        satellites[satellite.satellite_id] = satellite

    actions = [
        _parse_action(_require_mapping(item, f"solution.json.actions[{index}]"), index)
        for index, item in enumerate(actions_payload)
    ]
    return Solution(satellites=satellites, actions=actions)

# ===== from revisit_constellation/verifier/engine.py (unchanged) =====
"""Core verification logic for the revisit_constellation benchmark."""


from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import math

import brahe
import numpy as np



_BRAHE_EOP_INITIALIZED = False


def _ensure_brahe_ready() -> None:
    global _BRAHE_EOP_INITIALIZED
    if _BRAHE_EOP_INITIALIZED:
        return

    # Use a static zero-valued EOP provider so the verifier stays deterministic
    # and offline-friendly during early benchmark development.
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


def _isoformat_z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _angle_between_deg(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    norm_a = np.linalg.norm(vector_a)
    norm_b = np.linalg.norm(vector_b)
    if norm_a < NUMERICAL_EPS or norm_b < NUMERICAL_EPS:
        return 0.0
    cosine = float(np.dot(vector_a, vector_b) / (norm_a * norm_b))
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def _observation_midpoint(action: Action) -> datetime:
    return action.start + ((action.end - action.start) / 2)


def _initial_altitude_m(state_eci_m_mps: np.ndarray) -> float:
    return float(np.linalg.norm(state_eci_m_mps[:3]) - brahe.R_EARTH)


def _initial_orbital_elements(
    state_eci_m_mps: np.ndarray,
) -> tuple[float, float, float, float]:
    position_m = np.asarray(state_eci_m_mps[:3], dtype=float)
    velocity_m_s = np.asarray(state_eci_m_mps[3:], dtype=float)
    radius_m = float(np.linalg.norm(position_m))
    speed_m_s = float(np.linalg.norm(velocity_m_s))
    if radius_m <= NUMERICAL_EPS:
        raise ValueError("initial position magnitude must be positive")

    mu_m3_s2 = brahe.GM_EARTH
    specific_energy_m2_s2 = (0.5 * speed_m_s * speed_m_s) - (mu_m3_s2 / radius_m)
    if specific_energy_m2_s2 >= 0.0:
        raise ValueError("initial state is not a bound Earth orbit")

    semi_major_axis_m = -mu_m3_s2 / (2.0 * specific_energy_m2_s2)
    radial_velocity_m2_s = float(np.dot(position_m, velocity_m_s))
    eccentricity_vector = (
        ((speed_m_s * speed_m_s) - (mu_m3_s2 / radius_m)) * position_m
        - (radial_velocity_m2_s * velocity_m_s)
    ) / mu_m3_s2
    eccentricity = float(np.linalg.norm(eccentricity_vector))
    if semi_major_axis_m <= 0.0 or eccentricity >= 1.0:
        raise ValueError("initial state is not a closed elliptic orbit")

    perigee_altitude_m = (semi_major_axis_m * (1.0 - eccentricity)) - brahe.R_EARTH
    apogee_altitude_m = (semi_major_axis_m * (1.0 + eccentricity)) - brahe.R_EARTH
    return semi_major_axis_m, eccentricity, perigee_altitude_m, apogee_altitude_m


def _action_sample_times(start: datetime, end: datetime, step_sec: float) -> list[datetime]:
    if end <= start:
        return [start]
    points = [start]
    current = start
    delta = timedelta(seconds=step_sec)
    while current + delta < end:
        current = current + delta
        points.append(current)
    return points


def _interval_contains(instant: datetime, start: datetime, end: datetime) -> bool:
    return start <= instant < end


def _is_sunlit(position_eci_m: np.ndarray, epoch: brahe.Epoch) -> bool:
    sun_position = np.asarray(brahe.sun_position(epoch), dtype=float)
    sun_hat = sun_position / np.linalg.norm(sun_position)
    projection = float(np.dot(position_eci_m, sun_hat))
    perpendicular = np.linalg.norm(position_eci_m - (projection * sun_hat))
    return not (projection < 0.0 and perpendicular < brahe.R_EARTH)


def _slew_time_sec(angle_deg: float, attitude_model: AttitudeModel) -> float:
    angle_deg = max(0.0, angle_deg)
    if angle_deg <= NUMERICAL_EPS:
        return 0.0

    max_velocity = attitude_model.max_slew_velocity_deg_per_sec
    max_accel = attitude_model.max_slew_acceleration_deg_per_sec2
    if max_velocity <= 0.0 or max_accel <= 0.0:
        return math.inf

    ramp_time = max_velocity / max_accel
    triangular_threshold = (max_velocity * max_velocity) / max_accel
    if angle_deg <= triangular_threshold:
        return 2.0 * math.sqrt(angle_deg / max_accel)
    cruise_angle = angle_deg - triangular_threshold
    return (2.0 * ramp_time) + (cruise_angle / max_velocity)


def _build_propagators(
    instance: Instance, solution: Solution
) -> dict[str, brahe.NumericalOrbitPropagator]:
    epoch = _datetime_to_epoch(instance.horizon_start)
    end_epoch = _datetime_to_epoch(instance.horizon_end)
    force_config = brahe.ForceModelConfig(
        gravity=brahe.GravityConfiguration.spherical_harmonic(2, 0)
    )

    propagators: dict[str, brahe.NumericalOrbitPropagator] = {}
    for satellite in solution.satellites.values():
        propagator = brahe.NumericalOrbitPropagator.from_eci(
            epoch, satellite.state_eci_m_mps, force_config=force_config
        )
        propagator.propagate_to(end_epoch)
        propagators[satellite.satellite_id] = propagator
    return propagators


def _validate_satellites(
    instance: Instance, solution: Solution, errors: list[str]
) -> None:
    if len(solution.satellites) > instance.max_num_satellites:
        errors.append(
            f"Solution defines {len(solution.satellites)} satellites but the case allows at most "
            f"{instance.max_num_satellites}"
        )

    for satellite in solution.satellites.values():
        altitude_m = _initial_altitude_m(satellite.state_eci_m_mps)
        if altitude_m < instance.satellite_model.min_altitude_m - NUMERICAL_EPS:
            errors.append(
                f"Satellite {satellite.satellite_id} starts below min altitude: "
                f"{altitude_m:.3f} m < {instance.satellite_model.min_altitude_m:.3f} m"
            )
        if altitude_m > instance.satellite_model.max_altitude_m + NUMERICAL_EPS:
            errors.append(
                f"Satellite {satellite.satellite_id} starts above max altitude: "
                f"{altitude_m:.3f} m > {instance.satellite_model.max_altitude_m:.3f} m"
            )
        try:
            semi_major_axis_m, eccentricity, perigee_altitude_m, apogee_altitude_m = (
                _initial_orbital_elements(satellite.state_eci_m_mps)
            )
        except ValueError as exc:
            errors.append(f"Satellite {satellite.satellite_id} has invalid initial orbit: {exc}")
            continue
        if perigee_altitude_m < instance.satellite_model.min_altitude_m - NUMERICAL_EPS:
            errors.append(
                f"Satellite {satellite.satellite_id} has perigee below min altitude: "
                f"{perigee_altitude_m:.3f} m < {instance.satellite_model.min_altitude_m:.3f} m "
                f"(a={semi_major_axis_m:.3f} m, e={eccentricity:.9f})"
            )
        if apogee_altitude_m > instance.satellite_model.max_altitude_m + NUMERICAL_EPS:
            errors.append(
                f"Satellite {satellite.satellite_id} has apogee above max altitude: "
                f"{apogee_altitude_m:.3f} m > {instance.satellite_model.max_altitude_m:.3f} m "
                f"(a={semi_major_axis_m:.3f} m, e={eccentricity:.9f})"
            )


def _validate_action_structure(
    instance: Instance, solution: Solution, errors: list[str]
) -> dict[str, list[Action]]:
    actions_by_satellite: dict[str, list[Action]] = defaultdict(list)

    for index, action in enumerate(solution.actions):
        label = f"action[{index}]"
        if action.satellite_id not in solution.satellites:
            errors.append(f"{label} references unknown satellite_id {action.satellite_id!r}")
            continue
        if action.end <= action.start:
            errors.append(f"{label} must satisfy end > start")
        if action.start < instance.horizon_start or action.end > instance.horizon_end:
            errors.append(
                f"{label} lies outside the mission horizon: "
                f"{_isoformat_z(action.start)} to {_isoformat_z(action.end)}"
            )
        if action.action_type == "observation":
            if not action.target_id:
                errors.append(f"{label} observation is missing target_id")
            elif action.target_id not in instance.targets:
                errors.append(f"{label} references unknown target_id {action.target_id!r}")
        else:
            errors.append(
                f"{label} has unsupported action_type {action.action_type!r}; "
                "expected 'observation'"
            )
        actions_by_satellite[action.satellite_id].append(action)

    for satellite_id, actions in actions_by_satellite.items():
        actions.sort(key=lambda item: (item.start, item.end, item.action_type))
        for previous, current in zip(actions, actions[1:]):
            if previous.end <= current.start:
                continue
            errors.append(
                f"Satellite {satellite_id} has overlapping actions: "
                f"{previous.action_type} {_isoformat_z(previous.start)}-{_isoformat_z(previous.end)} "
                f"overlaps {current.action_type} {_isoformat_z(current.start)}-{_isoformat_z(current.end)}"
            )

    return actions_by_satellite


def _observation_geometry_ok(
    instance: Instance,
    target: Target,
    state_eci_m_mps: np.ndarray,
    state_ecef_m_mps: np.ndarray,
    epoch: brahe.Epoch,
) -> tuple[bool, str | None]:
    sensor = instance.satellite_model.sensor
    relative_enz = np.asarray(
        brahe.relative_position_ecef_to_enz(
            target.ecef_position_m,
            state_ecef_m_mps[:3],
            brahe.EllipsoidalConversionType.GEODETIC,
        ),
        dtype=float,
    )
    azimuth_elevation_range = np.asarray(
        brahe.position_enz_to_azel(relative_enz, brahe.AngleFormat.DEGREES),
        dtype=float,
    )
    elevation_deg = float(azimuth_elevation_range[1])
    slant_range_m = float(azimuth_elevation_range[2])

    if elevation_deg < target.min_elevation_deg - NUMERICAL_EPS:
        return (
            False,
            f"elevation {elevation_deg:.3f} deg below target minimum {target.min_elevation_deg:.3f} deg",
        )
    if slant_range_m > target.max_slant_range_m + NUMERICAL_EPS:
        return (
            False,
            f"slant range {slant_range_m:.3f} m exceeds target limit {target.max_slant_range_m:.3f} m",
        )
    if slant_range_m > sensor.max_range_m + NUMERICAL_EPS:
        return (
            False,
            f"slant range {slant_range_m:.3f} m exceeds sensor max range {sensor.max_range_m:.3f} m",
        )

    target_eci_m = np.asarray(
        brahe.position_ecef_to_eci(epoch, target.ecef_position_m),
        dtype=float,
    )
    line_of_sight = target_eci_m - state_eci_m_mps[:3]
    nadir = -state_eci_m_mps[:3]
    off_nadir_deg = _angle_between_deg(nadir, line_of_sight)
    if off_nadir_deg > sensor.max_off_nadir_angle_deg + NUMERICAL_EPS:
        return (
            False,
            f"off-nadir angle {off_nadir_deg:.3f} deg exceeds sensor max off-nadir angle "
            f"{sensor.max_off_nadir_angle_deg:.3f} deg",
        )

    return True, None


def _validate_action_geometry(
    instance: Instance,
    actions_by_satellite: dict[str, list[Action]],
    propagators: dict[str, brahe.NumericalOrbitPropagator],
    errors: list[str],
) -> list[ObservationRecord]:
    successful_observations: list[ObservationRecord] = []

    for satellite_id, actions in actions_by_satellite.items():
        propagator = propagators[satellite_id]
        for action in actions:
            sample_times = _action_sample_times(
                action.start, action.end, ACTION_SAMPLE_STEP_SEC
            )
            if action.action_type == "observation":
                target = instance.targets[action.target_id or ""]
                if action.duration_sec < target.min_duration_sec - NUMERICAL_EPS:
                    errors.append(
                        f"Observation for target {target.target_id} on {satellite_id} lasts "
                        f"{action.duration_sec:.3f} sec but requires at least "
                        f"{target.min_duration_sec:.3f} sec"
                    )
                    continue
                valid = True
                for sample in sample_times:
                    epoch = _datetime_to_epoch(sample)
                    state_eci = np.asarray(propagator.state_eci(epoch), dtype=float)
                    state_ecef = np.asarray(propagator.state_ecef(epoch), dtype=float)
                    ok, reason = _observation_geometry_ok(
                        instance, target, state_eci, state_ecef, epoch
                    )
                    if not ok:
                        errors.append(
                            f"Observation for target {target.target_id} on {satellite_id} is infeasible at "
                            f"{_isoformat_z(sample)}: {reason}"
                        )
                        valid = False
                        break
                if valid:
                    successful_observations.append(
                        ObservationRecord(
                            satellite_id=satellite_id,
                            target_id=target.target_id,
                            start=action.start,
                            end=action.end,
                            midpoint=_observation_midpoint(action),
                        )
                    )

    return successful_observations


def _target_vector_eci(
    target: Target, propagator: brahe.NumericalOrbitPropagator, instant: datetime
) -> np.ndarray:
    epoch = _datetime_to_epoch(instant)
    satellite_state_eci = np.asarray(propagator.state_eci(epoch), dtype=float)
    target_eci = np.asarray(
        brahe.position_ecef_to_eci(epoch, target.ecef_position_m),
        dtype=float,
    )
    return target_eci - satellite_state_eci[:3]


def _build_maneuver_windows(
    instance: Instance,
    actions_by_satellite: dict[str, list[Action]],
    propagators: dict[str, brahe.NumericalOrbitPropagator],
    errors: list[str],
) -> dict[str, list[ManeuverWindow]]:
    maneuver_windows: dict[str, list[ManeuverWindow]] = defaultdict(list)
    attitude_model = instance.satellite_model.attitude_model

    for satellite_id, actions in actions_by_satellite.items():
        observation_actions = [
            action for action in actions if action.action_type == "observation"
        ]
        observation_actions.sort(key=lambda action: action.start)
        propagator = propagators[satellite_id]

        for previous, current in zip(observation_actions, observation_actions[1:]):
            previous_target = instance.targets[previous.target_id or ""]
            current_target = instance.targets[current.target_id or ""]

            previous_vector = _target_vector_eci(
                previous_target, propagator, _observation_midpoint(previous)
            )
            current_vector = _target_vector_eci(
                current_target, propagator, _observation_midpoint(current)
            )
            slew_angle_deg = _angle_between_deg(previous_vector, current_vector)
            required_gap_sec = _slew_time_sec(
                slew_angle_deg, attitude_model
            ) + attitude_model.settling_time_sec
            actual_gap_sec = (current.start - previous.end).total_seconds()

            if actual_gap_sec + NUMERICAL_EPS < required_gap_sec:
                errors.append(
                    f"Satellite {satellite_id} needs {required_gap_sec:.3f} sec between observations "
                    f"but only has {actual_gap_sec:.3f} sec between {_isoformat_z(previous.end)} and "
                    f"{_isoformat_z(current.start)}"
                )
                continue

            window_start = current.start - timedelta(seconds=required_gap_sec)
            window = ManeuverWindow(
                satellite_id=satellite_id,
                start=window_start,
                end=current.start,
            )

            for action in actions:
                if action is previous or action is current:
                    continue
                if action.start < window.end and action.end > window.start:
                    errors.append(
                        f"Satellite {satellite_id} has action overlap with required maneuver/settling "
                        f"window before observation at {_isoformat_z(current.start)}"
                    )
                    break
            maneuver_windows[satellite_id].append(window)

    return maneuver_windows

def _simulate_resources(
    instance: Instance,
    actions_by_satellite: dict[str, list[Action]],
    maneuver_windows: dict[str, list[ManeuverWindow]],
    propagators: dict[str, brahe.NumericalOrbitPropagator],
    errors: list[str],
) -> None:
    resource = instance.satellite_model.resource_model
    sensor = instance.satellite_model.sensor
    attitude = instance.satellite_model.attitude_model

    for satellite_id, propagator in propagators.items():
        actions = actions_by_satellite.get(satellite_id, [])
        maneuvers = maneuver_windows.get(satellite_id, [])
        time_points = {
            instance.horizon_start,
            instance.horizon_end,
        }

        current = instance.horizon_start
        step_delta = timedelta(seconds=RESOURCE_STEP_SEC)
        while current < instance.horizon_end:
            time_points.add(current)
            current = min(current + step_delta, instance.horizon_end)
        time_points.add(instance.horizon_end)

        for action in actions:
            time_points.add(action.start)
            time_points.add(action.end)
        for maneuver in maneuvers:
            time_points.add(maneuver.start)
            time_points.add(maneuver.end)

        battery_wh = resource.initial_battery_wh

        sorted_points = sorted(time_points)
        for start, end in zip(sorted_points, sorted_points[1:]):
            duration_sec = (end - start).total_seconds()
            if duration_sec <= 0.0:
                continue

            midpoint = start + ((end - start) / 2)
            epoch = _datetime_to_epoch(midpoint)
            state_eci = np.asarray(propagator.state_eci(epoch), dtype=float)

            active_observation = next(
                (
                    action
                    for action in actions
                    if action.action_type == "observation"
                    and _interval_contains(midpoint, action.start, action.end)
                ),
                None,
            )
            active_maneuver = any(
                _interval_contains(midpoint, maneuver.start, maneuver.end)
                for maneuver in maneuvers
            )

            discharge_w = resource.idle_discharge_rate_w

            if active_observation is not None:
                discharge_w += sensor.obs_discharge_rate_w
            if active_maneuver:
                discharge_w += attitude.maneuver_discharge_rate_w

            charge_w = (
                resource.sunlight_charge_rate_w if _is_sunlit(state_eci[:3], epoch) else 0.0
            )

            battery_wh += ((charge_w - discharge_w) * duration_sec) / 3600.0

            if battery_wh < -NUMERICAL_EPS:
                errors.append(
                    f"Satellite {satellite_id} depletes battery below zero around {_isoformat_z(midpoint)}"
                )
                break

            battery_wh = min(resource.battery_capacity_wh, battery_wh)


def _compute_metrics(
    instance: Instance, successful_observations: list[ObservationRecord], satellite_count: int
) -> dict[str, Any]:
    observations_by_target: dict[str, list[datetime]] = defaultdict(list)
    for observation in successful_observations:
        observations_by_target[observation.target_id].append(observation.midpoint)

    target_gap_summary: dict[str, dict[str, float]] = {}
    target_capped_max_gaps: list[float] = []
    target_max_gaps: list[float] = []
    threshold_violation_count = 0

    for target_id, target in instance.targets.items():
        unique_midpoints = sorted(set(observations_by_target.get(target_id, [])))
        times = [instance.horizon_start, *unique_midpoints, instance.horizon_end]
        gaps_hours = [
            (right - left).total_seconds() / 3600.0
            for left, right in zip(times, times[1:])
        ]
        max_gap = max(gaps_hours)
        target_gap_summary[target_id] = {
            "max_revisit_gap_hours": max_gap,
            "observation_count": len(unique_midpoints),
            "expected_revisit_period_hours": target.expected_revisit_period_hours,
        }
        target_capped_max_gaps.append(
            max(max_gap, target.expected_revisit_period_hours)
        )
        target_max_gaps.append(max_gap)
        if max_gap > target.expected_revisit_period_hours:
            threshold_violation_count += 1

    return {
        "capped_max_revisit_gap_hours": (
            sum(target_capped_max_gaps) / len(target_capped_max_gaps)
            if target_capped_max_gaps
            else 0.0
        ),
        "worst_target_capped_max_revisit_gap_hours": (
            max(target_capped_max_gaps) if target_capped_max_gaps else 0.0
        ),
        "max_revisit_gap_hours": max(target_max_gaps) if target_max_gaps else 0.0,
        "threshold_violation_count": threshold_violation_count,
        "num_satellites": satellite_count,
        "target_gap_summary": target_gap_summary,
    }


def verify(instance: Instance, solution: Solution) -> VerificationResult:
    _ensure_brahe_ready()

    errors: list[str] = []
    warnings: list[str] = []

    _validate_satellites(instance, solution, errors)
    actions_by_satellite = _validate_action_structure(instance, solution, errors)
    if errors:
        return VerificationResult(is_valid=False, errors=errors, warnings=warnings)

    propagators = _build_propagators(instance, solution)
    successful_observations = _validate_action_geometry(
        instance, actions_by_satellite, propagators, errors
    )
    maneuver_windows = _build_maneuver_windows(
        instance, actions_by_satellite, propagators, errors
    )
    if errors:
        return VerificationResult(is_valid=False, errors=errors, warnings=warnings)

    _simulate_resources(
        instance, actions_by_satellite, maneuver_windows, propagators, errors
    )
    if errors:
        return VerificationResult(is_valid=False, errors=errors, warnings=warnings)

    metrics = _compute_metrics(instance, successful_observations, len(solution.satellites))
    return VerificationResult(
        is_valid=True,
        metrics=metrics,
        errors=errors,
        warnings=warnings,
    )


def verify_solution(case_dir: str | Path, solution_path: str | Path) -> VerificationResult:
    try:
        instance = load_case(case_dir)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        return VerificationResult(is_valid=False, errors=[f"Failed to load case: {exc}"])

    try:
        solution = load_solution(solution_path)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        return VerificationResult(is_valid=False, errors=[f"Failed to load solution: {exc}"])

    return verify(instance, solution)
