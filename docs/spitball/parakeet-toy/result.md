# Spitball result: a new toy for a parakeet

**Value criterion:** a physical object or setup a pet budgie would voluntarily
and repeatedly engage with, offering novel stimulation beyond standard cage toys.
**Method:** 12-agent blind panel (measured) mapped 8 obvious clusters; 40
candidates sampled toward the band, 12 in band; ranked by kernel
(`0.6·fringe + 0.4·value`). Value scores are judgment, not observed bird
behavior.

## Ranked (band)

| # | Toy | v | f |
|---|-----|---|---|
| 1 | **Summon Cord**: a perch-side pull lever on a stainless bead chain, run through rigid tubing outside the cage, that rings a bell beside the owner across the room, so the bird can call its flock on demand. | 0.80 | 0.80 |
| 2 | **Window Watch**: a perch at a window with a wild-bird feeder outside the glass. | 0.65 | 0.80 |
| 3 | **Lazy Susan Perch**: a turntable platform the bird spins by walking along its rim. | 0.60 | 0.80 |
| 4 | **Drop Chute**: the bird drops a light ball into a funnel at head height; it rattles down a chime spiral into a cup at foot level on the same perch, ready for the next drop. | 0.80 | 0.55 |
| 5 | **Pocket Jungle**: a potted bird-safe herb or spider plant to clamber through and nibble. | 0.70 | 0.60 |

Why each fulfills / why it isn't obvious:

1. **Summon Cord**: budgies are contact-calling flock birds; this gives the call
   a physical effect (the owner comes). Every panel toy is self-contained in the
   cage; none reaches the owner. Sits on the SELF-MOTIVATED fringe: the payoff
   is the owner, but the bird initiates. Mechanical, no electronics; the chain stays in tubing, no cord in reach.
2. **Window Watch**: live flock-watching for a social species. A setup rather
   than an object, so it leans on the PHYSICAL fringe ("budgie TV"). Risk:
   hawks or cats at the glass may stress rather than entertain; value scored low
   for that.
3. **Lazy Susan Perch**: self-propelled motion, a different kind from the
   panel's bouncy perches (instability). Hugs the BUDGIE-FIT fringe (the hamster
   wheel), but a flat turntable has no trap points. Least certain the bird
   cares; lowest value in band.
4. **Drop Chute**: exploits the drop-it-and-watch habit; the spiral returns the
   ball within reach, defeating the REPEATED failure (a dropped toy stays on
   the floor). Nearest
   panel cluster is foot-toy (carry and toss), but the reward here is the
   fall and the sound, not carrying.
5. **Pocket Jungle**: a living, three-dimensional thing to explore and graze.
   Nothing in 96 panel answers was alive. On the REPEATED fringe: a budgie will
   eventually strip it, so it needs rotation. Plant and soil must be untreated.

Below the cut (in band): Seed-Head Meadow (live grass grown to seed, the
highest-value candidate at 0.85 but far from the fringe), Budgie Piano, Seed-Head
Carousel, Rustle Room, Rainstick Perch, Chime Gate, Flap Door.

Cut as obvious despite high value: Answering Box and Echo Tube (pseudo-flockmate,
same mechanism as the mirror), Pull-Up Bucket and Budgie Mailbox (hidden food),
Salad Chandelier (shred-chew). Cut by constraint: Call Button Board (chewable
wiring), Snuggle Hut and Budgie Decoy (fibers; the decoy is also the
pair-bond sense-swap), Bubble Chase, Zipper Pull, Mini Hamster Wheel.

## What the panel made obvious (rejected)

`hidden-food-foraging` 12/12 · `mirror-social` 12/12 · `bead-manipulate` 12/12 ·
`shred-chew` 11 · `climb` 9 · `bath` 8 · `bouncy-perch` 6 · `foot-toy` 3

The panel was close to unanimous: four clusters hit 12/12, and most lists were
the same pet-store catalog in a different order (mirror swing, piñata, bead
abacus, puzzle box, bell ladder). `hidden-food-foraging` merges two raw clusters
(tear-open containers and lid/drawer puzzles), both 12/12, since both work
through the foraging drive. Below cutoff: hanging noisemakers (2), tunnel (1).
Shared grammar: **a self-contained object inside the cage that the bird acts on
alone**. The band lies outside that: toys that reach the owner, the window,
gravity, or something alive.

## Negative fringe (compass)

| Drops | Kind | Landmark |
|---|---|---|
| PHYSICAL | leave-one-out | no object: training routine, sound or video feed |
| BUDGIE-FIT | leave-one-out | toy for another species or a large parrot (hamster wheel, cat wand) |
| SELF-MOTIVATED | leave-one-out | owner-driven or for the owner's amusement (trick props, harness) |
| REPEATED | leave-one-out | one-shot novelty, consumed or habituated |
| NOVEL | leave-one-out | standard bell, mirror, ladder |
| SELF-MOTIVATED | sense-swap | "love" as pair bond: decoy mate, nest hideaway (hormonal trigger) |
| BUDGIE-FIT | sense-swap | "toy" as figurine: plush budgie for a person |

Full map: [map.json](map.json). All 40 candidates with cut reasons:
[candidates.jsonl](candidates.jsonl).
