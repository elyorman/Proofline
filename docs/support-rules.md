# Support rules

The Verifier sets a card's support level from its primary cause's evidence (spec §9.2). The numbers below live in [`agents/verifier/rules.py`](../agents/verifier/rules.py) and come from the dev split only: 40 dev matches with nothing planted, built with the planted classes' starting styles.

**Effect bands.** A metric's band is the 90th percentile of its absolute change from the first half, in its threshold units (absolute for rates and shares, a fraction of the first-half rate for sprint counts, km/h for sprint speed). A change of at least one band is **clear**; at least two bands is **large**.

| Metric | Subject | 5-minute window | 10-minute window |
|---|---|---|---|
| Pressure rate | team | 0.204 | 0.160 |
| Long-ball share | team | 0.145 | 0.117 |
| Sprint count (relative) | team / unit / player | 0.491 / 0.630 / 1.000 | 0.415 / 0.541 / 0.763 |
| Sprint speed (km/h) | team / unit / player | 1.67 / 2.11 / 2.69 | 1.44 / 1.76 / 2.31 |

**Minimum samples.** Pressure rate: 8 opponent actions in the zone. Long-ball share: 8 passes. Sprint count: 10 sprints by the subject in the first half, since a fall in sprints thins the window by design. Sprint speed: 3 sprints in the window. Channel shares have no band yet and are not published.

| Support level | Rule |
|---|---|
| strong | Large effect, sample at least twice the minimum, no counter-test weakened it, no contradiction |
| moderate | Clear effect, sample at least 1.25 times the minimum, survived or only weakened |
| weak | Anything else above the minimum: a small effect, a near-minimum sample |
| not published | Below the minimum sample, refuted, or contradicted |

**Contradiction scan.** A related metric moving the other way by at least its band contradicts a claim: the pressing team's pressure rate and the opponent's long-ball share move together, and so do a subject's sprint count and sprint speed.
