# AstroAgentBench, and how its simulation judges a plan

[AstroAgentBench](https://github.com/Mtrya/AstroAgentBench) ([paper, arXiv 2601.11354](https://arxiv.org/abs/2601.11354))
is a benchmark of space-mission planning tasks for AI agents. It has seven task families: AEOSSP (agile Earth-observation
scheduling), Revisit Constellation, Relay Constellation, Regional Coverage, Stereo Imaging, SatNet and SPOT-5. Each family
has train and test missions, reference solvers, and an **official verifier**: a physics simulator that replays a submitted
plan and returns valid/invalid plus metrics. The paper reports five coding agents (Codex CLI + GPT-5.4, Kimi CLI + Kimi K2.6,
OpenCode + DeepSeek V4 Pro, Claude Code + Claude Opus 4.6, OpenCode + MiniMax M2.7) against the reference solvers.

We used two families. In both, **the verifier is the only judge**. We merged each verifier into one file without changing
code (`data/flatten_*.py`) and check byte-identity against the official source (`make check-verifiers`).

## AEOSSP: what the verifier simulates
* **Orbits:** each satellite is propagated with SGP4 (brahe) from the mission's satellite definitions; positions are Earth-fixed.
* **Photo validity:** inside the task's time window, exact duration, matching sensor type, line of sight and off-nadir limit.
* **Turning the camera:** between two photos on one satellite there must be time to slew (speed and acceleration limits)
  and settle.
* **Battery:** idle power always; imaging power during photos; slewing power during turns; solar charging in sunlight;
  capped at capacity. **If any battery drops below 0 Wh, the whole plan is invalid (score 0).**
* **Score** (paper formula): N = 100 (0.45 WCR + 0.20 CR + 0.20 [1 - TAT/H] + 0.15 [1 - PC/E]), with weighted completion
  WCR, completion CR, mean turnaround TAT, power used PC, horizon H, total battery capacity E.

## Revisit Constellation: what the verifier simulates
* **Orbits:** the plan gives each satellite's position and velocity at mission start; the verifier propagates them with
  Earth gravity including J2 over 48 h; perigee and apogee must stay in the 500-900 km band.
* **Photo validity:** sampled every 10 s: elevation, slant range and off-nadir angle within limits; minimum duration.
* **Turning and battery:** slew + settle between photos; battery never below 0.
* **Revisit gap:** for each target, the longest time between consecutive photo midpoints (mission start and end count).
  Each target must stay within its requirement (6 or 8 h). Fewer satellites are better (cap 16-20).
* **Our per-mission score** (the paper does not publish its 0-100 anchors): if any target misses, 70 x mean phi(gap);
  otherwise 70 + 30 (cap - n) / (cap - 1). We also report the paper's own native metric (mean requirement-floored gap and
  satellite count) for comparison with the published agents.
