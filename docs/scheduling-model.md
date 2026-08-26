# Scheduling model

## Decision problem

Each order operation must be assigned a compatible machine, a qualified operator,
and a non-overlapping interval inside the 14-day calendar. Operations follow their
routing precedence and cannot begin before material release. Maintenance,
breakdowns, power windows, shift attendance, and existing frozen work remove
capacity. Family transitions consume sequence-dependent changeover time.

## Hard constraints

1. Exactly one selected machine alternative per scheduled operation.
2. No overlap on a machine or operator.
3. Routing precedence between consecutive operations.
4. Capability and operator qualification for every assignment.
5. Start after material arrival and inside available production calendars.
6. No overlap with maintenance/breakdown; power requires grid or generator capacity.
7. Completed operations remain frozen during replanning.

The validator independently checks the resulting plan before it can be returned as
valid. This is deliberately separate from the optimizer: a solver status alone is
not treated as proof that transformed real-world data remained consistent.

## Three objective modes

- **CHEAPEST** minimizes labour, overtime, generator, setup, operating, and expected
  lateness cost. It may accept modest lateness when recovery costs more than penalties.
- **MOST_ON_TIME** strongly weights weighted tardiness, especially for Tier-1/JIT
  work, while still pricing recovery actions.
- **MOST_ROBUST** adds load and health exposure penalties, protects bottleneck slack,
  and biases high-risk or strategic work earlier. Reserve capacity makes the schedule
  less brittle rather than simply leaving arbitrary empty time.

The selected plan is the one with the best risk-adjusted profit for the current
factory state, subject to strategic Tier-1 guardrails.

## Solve-time fallback

CP-SAT receives a bounded solve time. If a full solve is unavailable, the documented
bottleneck-aware dispatch heuristic ranks ready operations by customer weight,
penalty, slack, processing time, and setup affinity. Both paths feed the same validator
and financial engine; an invalid plan is never labelled feasible.

