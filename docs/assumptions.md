# Assumptions and model limits

- The planning horizon is 14 days with two eight-hour base shifts per day.
- Quantities are processed as operation batches. Batch splitting is only introduced
  for explicitly partial RFQ recommendations or rework.
- Processing durations include deterministic run time; quality, failure, absence,
  and material uncertainty are applied as risk costs/confidence simulations.
- A scheduled operation needs one qualified operator. Inspection resources are
  represented as machines so their finite capacity is enforced consistently.
- Grid events are known planning windows. Generator operation is allowed only within
  its capacity and when the economic decision rule justifies it for the chosen mode.
- Sequence-dependent setup time is based on part-family transitions: 20 minutes for
  the same family, 60 for related families, and 180 for a fixture/family change.
- Costs are demonstration assumptions configured centrally in INR, not claims about
  Sridhar Precision Works' actual commercial data.
- Health risk is an explainable rule using utilization, hours since maintenance,
  failure rate, MTBF, and MTTR. It is not presented as trained machine learning.
- Delivery confidence is a deterministic seeded risk simulation/estimate and should
  be recalibrated against MES, maintenance, quality, and supplier history before use.

SmartForge is a decision-support digital twin, not a safety-control or autonomous
machine-control system. A planner must approve schedule and customer commitments.

