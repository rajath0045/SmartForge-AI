# Live defense guide

## What did you build?

SmartForge is an AI-assisted production decision-support system for a finite-capacity
machine shop. It combines a deterministic operational digital twin, constraint
optimization, financial evaluation, scenario simulation, and explainable rules. It
does not claim that every rule is machine learning.

## Why this architecture?

A React client and FastAPI modular monolith are fast to run and easy to defend in an
assessment. The boundaries between persistence, scheduling, validation, costs, and
HTTP are explicit, so the solver can later move to an asynchronous worker and SQLite
can be replaced by PostgreSQL without rewriting the UI or business model. Separate
microservices would add deployment and consistency costs before they add value at a
40-person factory scale.

## Why OR-Tools CP-SAT?

Job-shop scheduling is combinatorial: assigning operations, ordering them, selecting
eligible machines, and respecting calendars creates many discrete choices. CP-SAT is
designed for interval and Boolean constraints, supports no-overlap scheduling, returns
solution status and bounds, and is production-tested. Linear spreadsheet-style
capacity arithmetic cannot prove that individual jobs fit without collisions.

## What optimization problem is being solved?

For every unfinished operation, choose a compatible machine/operator and start/end
interval over a 14-day horizon. Respect routing precedence, finite machine and labour
capacity, material release, maintenance/breakdowns, shift and power calendars, and
family changeovers. Minimize a policy-specific weighted cost that includes tardiness,
operating cost, overtime, energy/generator use, setups, and risk exposure.

## Why does sequence matter?

Switching between part families needs setup. Same-family work takes about 20 minutes,
related families 60, and a fixture/family change 180. Therefore A→B→C can consume a
different total capacity than A→C→B. Grouping compatible families frees productive
hours, but the optimizer must trade that gain against due dates and customer penalties.

## How are operators represented?

An operation needs both a machine and one present, qualified operator. Operator
intervals cannot overlap. A free grinder is not capacity if all three qualified
grinder operators are absent, assigned elsewhere, or outside their shift. This is why
the capacity view reports both equipment hours and skill-constrained hours.

## How are power cuts handled?

Known grid outages remove powered capacity. Generator use is an explicit recovery
choice bounded by generator capacity and machine consumption. The recommendation
compares avoided penalty plus protected contribution margin against diesel and added
operating cost. It can rationally say either “run” or “do not run” the generator.

## How is overtime compared with penalties?

Both are expressed in INR in the same objective. Overtime is chosen when its fully
loaded cost—including labour multiplier, machine and energy cost, and any additional
changeover—is less than the expected loss it prevents. Tier weight raises the cost of
strategic lateness but does not make overtime economically unlimited.

## What happens after a breakdown?

The replan freezes completed work, preserves already-started work when feasible,
blocks the failed machine for the repair interval, and optimizes only the remaining
operations. An independent diff reports moved jobs, machine/shift changes, new
completion dates, overtime/generator changes, and incremental disruption cost. The
old plan stays available for audit.

## How does capable-to-promise/order acceptance work?

The RFQ is temporarily inserted into the same constrained factory state as committed
orders. SmartForge tests requested-date feasibility and recovery alternatives, then
calculates risk-adjusted contribution after production, overtime, energy, setup,
generator, rework, failure, and expected penalty costs. It also measures penalty
displacement on existing orders. The result is ACCEPT, conditional recovery,
negotiated date, partial delivery, outsource, or REJECT—with named constraints and a
financial bridge.

## Why can cheapest differ from most profitable?

The cheapest operating plan can save overtime but trigger a larger late penalty or
lose protected contribution. Profit is revenue minus all production and risk costs;
cost minimization that ignores delivery consequences is incomplete. SmartForge shows
production cost and expected profit separately.

## How is robustness measured?

The robust policy prices high utilization, machine health exposure, low delivery
slack, and single-skill dependency, and protects reserve on the bottleneck. Seeded
uncertainty trials/estimates convert failure, absence, material, and quality risk into
delivery confidence. Robustness is therefore observable slack and reduced expected
loss, not an unexplained “AI score.”

## Is this predictive maintenance ML?

No. The demo health score is an explainable deterministic rule using hours since
maintenance, utilization, failure count, MTBF, and MTTR. With real timestamped sensor
and work-order history, survival analysis or calibrated gradient boosting could be
evaluated. Calling the seeded rule ML would weaken the technical claim.

## Where would ML genuinely help?

- Calibrated failure hazard from sensor and maintenance history.
- Supplier lead-time and absenteeism distributions.
- Operation-duration and rework probability by part/process context.
- Demand forecasting for tactical capacity investment.

ML should estimate uncertain inputs; constraint optimization should still produce the
feasible schedule.

## What would change with real factory data?

Integrate ERP/MES order and routing masters, machine state, attendance, maintenance,
quality, and power meters; calibrate setup and duration distributions; add planner
override feedback; validate costs with finance; introduce authentication/audit; and
run shadow planning before any live commitments.

## How would this scale?

Move to PostgreSQL, enqueue solve requests, snapshot immutable inputs, cache analytics,
and use rolling horizons/decomposition by bottleneck or product family. CP-SAT receives
a time limit and returns the best incumbent. The documented dispatch heuristic can
provide a fast feasible plan, but it must pass the same validator.

## What if optimization takes too long?

Keep the last valid incumbent, report solve status/gap rather than pretending it is
optimal, and fall back to bottleneck-aware dispatch (weighted due date, penalty, slack,
processing time, and setup affinity). A plan is published only after validation.

## What should the owner do if GRIND-01 breaks?

First confirm repair time and freeze current work. Replan the remaining horizon. If
overtime after repair protects more value than it costs, approve it; otherwise compare
qualified outsourcing and a negotiated extension with the most flexible affected
customer. The “Owner's Next Call” identifies the party whose response releases the
most constrained grinding hours and quantifies the protected Tier-1 value.

## Honest limitations

The demo uses generated durations and risk distributions, simplified batch operations,
one operator per operation, and deterministic known calendars. It is decision support,
not autonomous dispatch. These limits are explicit so the implemented constraints and
financial logic remain technically defensible.

