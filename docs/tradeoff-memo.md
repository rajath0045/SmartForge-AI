# Management trade-off memo

**To:** Works owner and production manager  
**Subject:** Selecting the two-week production policy  
**Decision horizon:** Current seeded 14-day plan

SmartForge evaluates the same committed demand under three policies. The figures in
the live application are calculated from the active schedule; they are not static
memo inputs. Management should normally adopt **Most Robust** while the single
grinding resource is heavily loaded. It gives up a small amount of theoretical
short-term margin to protect Tier-1 delivery confidence and leaves recoverable
bottleneck capacity.

| Decision lens | Cheapest | Most On-Time | Most Robust |
|---|---|---|---|
| Primary objective | Lowest expected operating cost | Lowest weighted lateness | Best risk-adjusted profit |
| Overtime / generator | Used only below avoided-loss value | Used more readily for delivery protection | Used selectively before fragile periods |
| Bottleneck loading | Can run close to full capacity | High when it protects due dates | Reserve capacity is explicitly valued |
| Failure exposure | Highest | Medium | Lowest |
| Best use | Stable demand and healthy equipment | Immediate customer recovery | Current constrained shop conditions |

## Current deterministic comparison

The seeded 1–15 September horizon currently produces the following independently
validated heuristic schedules. Values are recalculated by
`GET /api/v1/schedule/comparison`; this table records the reproducible assessment
snapshot rather than replacing the live calculation.

| Metric | Cheapest | Most On-Time | Most Robust |
|---|---:|---:|---:|
| Production cost | ₹160.54L | ₹161.82L | ₹163.02L |
| Overtime cost | ₹3,438 | ₹15,570 | ₹1,332 |
| Late penalties | ₹0 | ₹0 | ₹0 |
| Generator cost | ₹0 | ₹0 | ₹0 |
| Changeover cost | ₹1.35L | ₹2.59L | ₹3.86L |
| On-time delivery | 100.0% | 100.0% | 100.0% |
| Expected profit | ₹417.66L | ₹416.38L | ₹415.18L |
| Modeled breakdown exposure | ₹5.77L · High | ₹5.53L · Medium | ₹4.07L · Low |
| Feasible / validator result | Yes / valid | Yes / valid | Yes / valid |

All three plans meet every current promise, so the decision is about economics under
uncertainty rather than deterministic lateness. Most Robust sacrifices ₹2.48L of
nominal profit versus Cheapest and reduces direct breakdown exposure by ₹1.70L. The
management utility applies a transparent 1.5× reliability factor for correlated
effects that the direct penalty estimate omits—expediting, downstream starvation and
customer escalation. That produces roughly ₹2.54L of protected value, slightly more
than the nominal sacrifice, so Most Robust is the present recommendation. If that
risk-aversion assumption changes, management can rationally select Cheapest instead.

## Why robust is the default recommendation

GRIND-01 is both a finite-capacity constraint and a single-machine dependency for
several routings. Loading it to 100% makes a short failure propagate through every
downstream inspection and delivery date. The robust policy moves strategic work
ahead of risky windows, avoids placing critical batches across maintenance, groups
compatible families where possible, and retains a small recovery buffer. This is
economically justified when the expected reduction in penalties and lost margin is
greater than the extra regular/overtime cost.

## When to override the recommendation

- Choose **Most On-Time** during a credible Tier-1 recovery event when the avoided
  penalty and protected relationship value exceed overtime, generator, and setup cost.
- Choose **Cheapest** only when machine health is stable, material arrivals are firm,
  bottleneck load is moderate, and no strategic commitment is exposed.
- Re-run the comparison after any breakdown, absence, material delay, power outage,
  or accepted RFQ; yesterday's best policy need not be today's best policy.

## Approval rule

Approve a recovery action when:

`avoided penalty + protected contribution margin + strategic risk value`

is greater than:

`overtime + generator + added setup + outsourcing + reliability exposure`.

The control tower presents both sides of this calculation and names the affected
orders. The planner remains accountable for the final commitment.
