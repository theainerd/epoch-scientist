# Ideas Muse proposed, in plain words

Each row is one attempt, in the order it finished. "Parent" is the program the attempt started from. Kept = valid on every development mission and better than its worker's best so far (a worker's first fully valid program is also kept). Scores are the development score from the frozen AstroAgentBench verifier. The plain-language labels are summaries of Muse's own hypotheses; Muse's original titles are in the last column.

## Problem 1 - Earth-observation scheduling (AEOSSP)

Start program dev score: 74.93

| # | Worker · cycle | Idea (plain words) | Parent | Dev score | Result | Muse's title |
|---|---|---|---|---|---|---|
| 1 | W2 · c1 | Pick photos by value per battery cost, then repair locally | start | 75.33 | kept | Battery-Aware Weighted Greedy with Repair and Local Search |
| 2 | W1 · c1 | Insert the photos you would most regret losing, then destroy-and-repair | start | 72.79 | kept | Battery-Aware Regret Greedy with Large-Neighborhood Repair |
| 3 | W1 · c2 | Re-optimise each satellite's photo sequence exactly | c1 | 73.67 | kept | Chain-DP Ejection Repair on Battery-Safe Insertion Core |
| 4 | W2 · c2 | Use the whole 60 s for adaptive destroy-and-repair | c1 | 76.07 | kept | Adaptive Regret LNS Using Full Time Budget Seeded From Best Greedy Plan |
| 5 | W1 · c3 | Wider exact re-optimisation that can bump low-value photos | c2 | 74.32 | kept | Density-Scored Widened Chain-DP with Cross-Satellite Ejection |
| 6 | W2 · c3 | Bump low-value photos to fit the heaviest missed ones | c2 | 76.46 | kept | Weight-First Ejection Chains With TAT-Disciplined Acceptance |
| 7 | W1 · c4 | Re-optimise time slices across 2-3 satellites together | c3 | 74.48 | kept | Multi-Satellite Segment DP with Heavy-Task Ejection Chains |
| 8 | W2 · c4 | Repeat the bumping with small random kicks; cap the delay | c3 | 76.60 | kept | Perturbed Iterated Ejection With Cumulative Turnaround Budget |
| 9 | W1 · c5 | Time-slice re-optimisation that respects neighbouring photos | c4 | 74.44 | discarded | Boundary-Aware Segment DP with Perturbed Iterated Ejection |
| 10 | W2 · c5 | Move photos earlier to cut the delay | c4 | 76.56 | discarded | TAT-Directed Retiming With CR-Guarded Heavy Ejection |
| 11 | W2 · c6 | Exhaustively re-time the weakest photos | c4 | 76.43 | discarded | Deadline-Exhaustive Weakest-First Repaid Retiming and Ejection |
| 12 | W1 · c6 | Reserve scarce opportunities for high-value photos | c4 | 74.48 | discarded | Scarcity-Aware Heavy-Task Reservation with Task-Preserving Relocation |
| 13 | W2 · c7 | Move blocked high-value photos to other satellites | c4 | 76.29 | discarded | Scarcity-Ordered Cross-Satellite Migration Rescue For Heavy Tasks |
| 14 | W1 · c7 | Put prices on scarce resources while building the plan | c4 | 75.12 | kept | Lagrangian-Priced Global Construction with Priced Segment DP |
| 15 | W2 · c8 | Adopt the pricing idea, and protect the bumping step | c4 | 76.63 | kept | Contention-Priced Construction With Protected Iterated Ejection |
| 16 | W1 · c8 | Add a price for delay | c7 | 74.74 | discarded | Latency-Aware Lagrangian Priced Construction with Cumulative TAT Budget |
| 17 | W2 · c9 | Delay budget plus a guarded choice between plans | c8 | 75.71 | discarded | TAT-Budgeted Weight-Aware Pricing With Pareto-Guarded Selection |
| 18 | W1 · c9 | Tune the delay price for each mission | c7 | 74.97 | discarded | WCR-First Priced Portfolio with Per-Mission Latency Selection and Loose TAT Ceiling |
| 19 | W2 · c10 | Restart the bumping from the best plan found | c8 | 76.30 | discarded | Seed-Anchored Election With Full-Budget Perturbed Ejection |
| 20 | W1 · c10 | Better price updates (averaged over rounds) | c7 | 75.15 | kept | Perturbed Priced Portfolio with Dual Averaging and Unguarded Exact Polish |

## Problem 2 - Revisit Constellation

Start program dev score: 69.82

| # | Worker · cycle | Idea (plain words) | Parent | Dev score | Result | Muse's title |
|---|---|---|---|---|---|---|
| 1 | W1 · c1 | Search many orbit layouts, then schedule photos by deadline | start | 0.00 | invalid on 1 of 4 missions | Deadline-Driven Fleet Pruning with Coverage-Optimized Walker Constellations |
| 2 | W2 · c1 | Choose orbits that match where the targets are | start | 45.13 | invalid on 1 of 4 missions | Targeted Coverage-Greedy Constellation Minimization |
| 3 | W2 · c2 | Same idea, but first build a safe back-up plan | start | 0.00 | kept | Runtime-First Lean Constellation with Guaranteed Fallback Return |
| 4 | W1 · c2 | Keep the baseline orbits, schedule by deadline, then remove satellites | start | 20.00 | kept | Cap-First Deadline Scheduling with Cheap Visibility-Based Pruning |
| 5 | W1 · c3 | Start from a quick safe plan, then improve it | c2 | 75.45 | kept | Baseline-First Cheap Seed, Then Deadline-Aware Improvement |
| 6 | W2 · c3 | Find and fix a sign error in its own camera-angle check | c2 | 76.63 | kept | Geometry-Verified Lean Greedy with Non-Empty Fallback |
| 7 | W1 · c4 | Remove satellites one at a time, re-planning all photos each time | c3 | 77.03 | kept | Reschedule-Aware Deep Pruning on a Guaranteed Cheap Seed |
| 8 | W2 · c4 | Add a few well-placed satellites, then prune | c3 | 76.63 | discarded | Targeted Pool Greedy to Cut Loose Fleets While Keeping Tight Feasibility |
| 9 | W1 · c5 | A smarter re-planner that looks ahead | c4 | 38.97 | invalid on 2 of 4 missions | Lookahead Repair Scheduler with Beam-Search Fleet Minimisation |
| 10 | W2 · c5 | Re-plan the photos of the most urgent places first | c3 | 76.63 | discarded | Scheduler-Aware Gap-Critical Rescheduling with Local Repair |
| 11 | W1 · c6 | Re-plan around the bottleneck photos | c4 | 77.03 | discarded | Slew-Audited Bottleneck Rescheduler on a Guaranteed Cheap Seed |
| 12 | W2 · c6 | Prune using fast orbit estimates with a safety margin | c3 | 73.47 | discarded | Fast-Only Margin-Verified Fleet Pruning with Phase-Diverse Walker Pool |
| 13 | W1 · c7 | Try more orbit spacings before pruning | c4 | 77.03 | discarded | Diverse-Phase Cached Pool with Seed-First Fleet Pruning |
| 14 | W2 · c7 | Prune by 'regret' with exact photo timing | c3 | 75.84 | discarded | Incremental Regret-Guided Pruning with Requirement-Exact Cached Scheduling |
| 15 | W1 · c8 | Build the fleet bottom-up from several orbit layouts | c4 | 77.42 | kept | Union-Pool Constructive Fleet Minimisation with Joint Compression Swaps |
| 16 | W2 · c8 | Replace two satellites with one better-placed satellite | c3 | 76.63 | discarded | Joint Pair-Replacement Fleet Reduction with Full-Cap Walker Variants |
| 17 | W1 · c9 | Choose the best moment inside each visibility window | c8 | 77.42 | discarded | Window-Time Optimised Scheduler for Tight-Revisit Fleet Compression |
| 18 | W2 · c9 | Flexible photo timing: shift neighbouring photos to make room | c3 | 77.03 | kept | Window-Flexible Slew-Aware Scheduling to Break the Tight Fleet Plateau |
| 19 | W1 · c10 | Redesign the orbit layout for the 6-hour missions | c8 | 77.42 | discarded | Walker Topology Redesign for Tight Six-Hour Revisit |
| 20 | W2 · c10 | Grow the fleet from many different orbit families | c9 | 77.82 | kept | Geometry-Diverse Constructive Growth for Six-Hour Revisit Compression |
