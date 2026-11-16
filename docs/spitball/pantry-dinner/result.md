# Spitball result: a dinner from a fixed pantry

**Request:** a dinner dish using only lentils, a lemon, eggs, stale bread.
**Pantry rule:** free extras are water, salt, oil, and any dried spice or dried
herb from a home spice rack (garlic/onion powder and mustard powder included).
Out: fresh aromatics, dairy, flour, sugar, vinegar, stock, baking soda.
**Value criterion:** a complete dinner, cookable with home equipment in under ~1
hour, that tastes good and uses only the pantry.
**Method:** 12-agent blind panel (measured) mapped 9 obvious clusters out of 10;
fringe-check run (no holes); 42 candidates sampled toward the band, 39 after
merging duplicates, 15 in band; ranked by kernel (`0.6·fringe + 0.4·value`).
Value scores are pre-cooking judgment by the same model that generated the
candidates. The cook test below is the external check.

## Headline finding

**The panel covered the familiar role space.** Each obvious cluster is a
distinct assignment of roles to ingredients (bread as crumb topping, thickener,
base layer, binder, salad body, custard matrix; egg as garnish, poached-in,
liaison, binder, set matrix), and 9 of the 10 cleared 25%, most at 50% or more.
The way out was to **change an ingredient's form**. All five ranked entries
do it with lentils (milled to flour) or bread (rebuilt as pasta, grain or
crust). The rest of the band does it with egg (whipped foam in the soufflé and
steamed sponge, cold emulsion in the gribiche) or bread (emulsion base in the
skordalia and cold soup). Technique upgrades that kept a familiar role (oil-confit
yolks on lentil toast, Scotch eggs, lentil carbonara with whole lentils) were
judged obvious and cut.

## Ranked (band)

| # | Dish | v | f |
|---|------|---|---|
| 1 | **Lentil panisse: whisk blender-milled red-lentil flour into simmering water with turmeric, cook thick like polenta, spread 1 cm in an oiled tray, chill until set (~30 min), cut into fries and pan-fry; serve with aioli whisked from yolk, oil, lemon and garlic powder (variant: squares with lemon-chili dressing and a fried egg, Shan-tofu style)** | 0.75 | 0.80 |
| 2 | **Red-lentil egg noodles alla carbonara: blender-mill dry red lentils to flour, knead with egg, rest, roll and cut; toss off heat with yolk, lemon and plenty of black pepper, fried bread cubes in place of guanciale (variants: with pangrattato and chili; in lentil broth with lemon-marinated soft eggs)** | 0.80 | 0.75 |
| 3 | **Passatelli in lentil broth: knead stale breadcrumbs, egg, lemon zest and nutmeg into a stiff dough, press through a potato ricer (or roll pencil-thin and cut) into the simmering lentil broth, serve noodles and lentils together** | 0.75 | 0.75 |
| 4 | **Hand-rolled bread 'fregola' pilaf: rub breadcrumbs with egg into small pellets, toast them in oil, then cook pilaf-style with lentils and spices** | 0.70 | 0.75 |
| 5 | **Breadcrumb pide: stale crumbs bound with egg pressed into a boat-shaped crust, filled with spiced lentils, an egg cracked in the middle, baked** | 0.65 | 0.75 |

Method (steps, no quantities), why each fulfills / why it isn't obvious:

1. **Lentil panisse.** Mill dry red lentils to flour in a blender. Whisk into
   simmering salted water with turmeric and cook thick, like polenta, ~10 min.
   Spread 1 cm thick in an oiled tray and chill until set (~30 min; the freezer
   is faster). Cut into fries and pan-fry crisp. Whisk yolk, oil, lemon juice
   and garlic powder into aioli. *Fulfills:* fried starch plus emulsion sauce
   is a full plate, and every element comes from the pantry. *Not obvious:*
   lentils become a set flour paste (the chickpea technique behind panisse and
   Shan tofu); no panelist ground the lentils. *Risk:* the set time sits on the
   1-hour edge, and a home blender may leave the flour gritty.
2. **Red-lentil carbonara.** Mill lentils to flour, knead with egg, rest 15 min,
   roll thin and cut. Boil 2–3 min. Toss off the heat with yolk, lemon and a
   lot of black pepper; fried bread cubes stand in for guanciale.
   *Fulfills:* a pasta dinner, with egg as both noodle binder and sauce.
   *Not obvious:* lentil as the noodle. The carbonara sauce on its own is
   obvious (egg-lemon liaison) and the version with whole lentils was cut.
   *Risk:* gluten-free dough tears, so roll it thicker than wheat pasta.
3. **Passatelli in lentil broth.** Simmer the lentils with spices and keep the
   broth. Knead breadcrumbs, egg, lemon zest and nutmeg into a stiff dough.
   Press it through a potato ricer, or roll pencil-thin and cut, straight into
   the simmering broth. Serve noodles and lentils together. *Fulfills:* a real
   Emilian dish whose only missing classic ingredient is parmesan; lemon zest
   and nutmeg are traditional in it. *Not obvious:* bread becomes the noodle.
   The panel's bread-in-soup ideas all dissolved the bread (ribollita) or laid
   it underneath (fatteh). *Risk:* without cheese the dough may need extra
   crumb to hold together.
4. **Bread "fregola" pilaf.** Rub breadcrumbs with beaten egg between your palms
   into small pellets, then dry and toast them in oil. Cook them pilaf-style
   with lentils, cumin and water, and finish with lemon. *Fulfills:* a
   one-pot grain dinner. *Not obvious:* bread rebuilt as a grain. It sits
   closest to the mujaddara cluster, which used bread only as a crumb topping.
   *Risk:* the pellets can turn to mush if overcooked.
5. **Breadcrumb pide.** Bind crumbs with egg and press into a boat-shaped crust
   on a tray. Par-bake it, fill with spiced dry-cooked lentils, crack an egg
   into the middle and bake until the egg sets. *Fulfills:* a hand-held
   baked dinner. *Not obvious:* bread rebuilt as a dough-like shell.
   *Risk:* the crust is crumbly rather than chewy, which is why its value is lowest.

Other in-band entries: canederli on lemony lentils, sauce gribiche on lentil
toast, skordalia-style bread sauce under crisp lentils, breadcrumb fried "rice",
lentil-egg crepes, red lentil soufflé, steamed lentil sponge, cold bread-emulsion
soup, lentil gnocchi, masabacha-style lentil purée. All are in `candidates.jsonl`.

## Cook test

Cook the top two (#1 and #2) plus one **obvious-set control** that the same
judge scored in the same range: mujaddara-style lentils with fried crumbs and a
fried egg, or avgolemono lentil soup (both 0.65–0.75). Rate all three on the
same scale. Without the control, the test shows only whether band dishes are
edible, not whether they beat the obvious set. #2 matters most for judge
calibration: it has the highest value score in the band and the likeliest
mechanical failure (hand-rolled gluten-free noodles), so don't swap it for
something safer.

| Dish | Cooked? | Tasted good (0–1) | Pantry held? | Under 1 h? | Notes |
|------|---------|-------------------|--------------|------------|-------|
| #1 panisse | | | | | |
| #2 lentil carbonara | | | | | |
| control (obvious set) | | | | | |

## The map (measured, N=12)

| Cluster (roles) | panelists |
|-----------------|-----------|
| bound-fritters (egg + crumb bind mashed lentils, fried) | 12 |
| eggs-poached-in-lentils (shakshuka logic) | 12 |
| mujaddara-crispy-topping (lentil pilaf, fried crumbs, fried egg) | 12 |
| egg-lemon-emulsion (avgolemono liaison) | 11 |
| lentil-pot-egg-garnish (soup/dal/curry, egg cooked separately) | 11 |
| bread-thickened-stew (ribollita/panade) | 8 |
| egg-set-bake (frittata, omelette, strata) | 7 |
| fatteh-over-bread (toasted base, lentils, egg on top) | 7 |
| bread-salad (panzanella/fattoush) | 6 |
| *migas (below cutoff)* | 1 |

Negative fringe (leave-one-out over `COMPLETE-DINNER`, `COOKABLE`,
`TASTES-GOOD`, `PANTRY-ONLY`): dessert/snack (lemon bread pudding);
multi-day prep (dosa, sprouting, cured yolks); a classic stripped of its
defining ingredient (ribollita with no vegetables; 9 panelists produced one of
these, the only near-miss cluster); one staple away (real shakshuka, mujaddara
with onions). Full map in `map.json`.
