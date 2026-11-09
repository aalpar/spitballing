# Spitball result: premises for a new Daria episode

**Value criterion:** unmistakably Daria (deadpan-cynic voice, Lawndale ensemble,
conformity/media/consumer satire), resolves in one ~22-minute episode, not an
aired premise.
**Method:** 12-agent blind panel (measured) mapped 10 obvious clusters; 39
candidates sampled toward the band; ranked by kernel (`0.6·fringe + 0.4·value`).
Candidates were scanned against one-line summaries of the aired list (65 episodes + 2 films); partial overlaps lowered value, none judged a retread. The top 5 were checked further against full synopses where overlap seemed possible.

## Ranked (band)

| # | Premise | v | f |
|---|---------|---|---|
| 1 | **Sincere**: Daria loses a bet and has to say only sincere things for a week, and nobody in Lawndale can tell the difference. | 0.82 | 0.78 |
| 2 | **Alibi**: Daria is accused of secretly taking Tiffany's SAT, and her only alibi is the earnest thing she was really doing that Saturday, which she'd rather be expelled than admit. | 0.78 | 0.74 |
| 3 | **GothAudit**: Andrea, the silent goth, calls Daria a poser misanthrope in public, and Daria ends up competing to prove her alienation is authentic. | 0.83 | 0.70 |
| 4 | **SaveSSW**: *Sick Sad World* faces cancellation, and Daria finds herself organizing a fan letter campaign. | 0.80 | 0.72 |
| 5 | **Weeding**: the public library culls books nobody checks out, so Daria borrows the doomed ones to save them, and realizes she's gaming a popularity metric exactly like the people she despises. | 0.84 | 0.68 |

Why each fulfills / why it isn't obvious:

1. **Sincere**: the satire target is that nobody listens; her voice survives because sincerity in her deadpan reads as sarcasm. Every panel premise has something *happen to* Daria. Here the constraint is on her voice itself, which sits right at the VOICE fringe. Nearest canon is *The F Word*: there Jane takes on an off-type persona for an assignment, while Daria's own task was getting Quinn grounded (checked against the Outpost Daria synopsis). The mechanism is adjacent, but the premise isn't aired.
2. **Alibi**: an accusation plot with a hidden-sincerity reveal, set off by Tiffany, whom the panel never used. Nearest canon is the cheating scandal in *Murder, She Snored*, but that episode is a dream parody about suspicion, not about an alibi she's ashamed of.
3. **GothAudit**: makes authenticity in a subculture the target and turns Daria's own pose into the thing on trial. Andrea appears in 0 of 96 panel answers. The closest panel idea (a substitute who agrees with Daria, 1/12) is a foil, not a challenge to her legitimacy.
4. **SaveSSW**: Daria becomes the earnest fan activist she'd mock, for the trashiest show on TV. Every panel use of *Sick Sad World* was as a camera crew or a lawsuit, never as the thing she's attached to.
5. **Weeding**: a non-school setting where Daria acts first, satirizing metrics as popularity. It's the most structurally distant from the map: no institution imposes anything and no parent intrudes.

Below the cut: OnHold (a bottle episode on hold with the phone company), AmandaSculpts, Amends.

## What the panel made obvious (rejected)

`jane_art` 12/12 · `school_imposes` 12/12 · `parents_intrude` 10 ·
`daria_work_public` 9 · `viral_shallow` 8 · `band` 7 · `demartino_temper` 6 ·
`kb_breakup` 6 · `quinn_hidden_depth` 5 · `trapped` 4

The panel converged hard: two clusters were unanimous. Its shared grammar is that
**an institution or parent acts and Daria reacts**. AI hall monitors alone showed
up in 7 of 12 lists. Several obvious clusters already aired: *The Lost Girls*
(`daria_work_public`), *Fizz Ed* (`school_imposes`), *Psycho Therapy*
(`parents_intrude`), *Quinn the Brain*, *Antisocial Climbers* (`trapped`). So
"obvious" here also often means "already made".

## Negative fringe (compass)

- VOICE: Daria written sincere / VOICE (sense-swap): cynic as mean snark
- LAWNDALE: Daria alone among strangers
- SATIRE: hangout or sitcom-mechanics plot, not about anything
- EPISODE_SCALE: needs a movie or serial arc
- NOT_AIRED: an aired premise

The top two hug VOICE: each threatens Daria's register and keeps it intact
because of how the premise is built.

## Caveats

- **Generation and judging were both done by the conductor**, not fanned out to
  separate agents. The value and fringe scores are one judge's calls, and the
  candidates were written with the map in view.
- **Fringe-check skipped** (quick run).
- **Era left open** per the brief. Census and BallotMeasure assume a 2000-era,
  season-5 Daria; none of the top 5 depend on era.
- **Siblings:** MostAverage, TestMarket, and Nielsen are one vein (Lawndale as
  statistical average) and all fall below the cut.

Full audit: `candidates.jsonl` (39 candidates, 30 in band), `map.json`.
