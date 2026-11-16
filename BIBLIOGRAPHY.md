# Bibliography

Two parts: works this repo cites or uses by name, and related work it does
not cite but parallels or is exposed to. Each entry names where it bears on
the repo. Citations checked against publisher or index records on 2026-11-15
(Krippendorff's edition and year taken from the repo's own citation).
Annotations rest on abstracts or standard secondary accounts, not full text.

## Cited or used by name

### Definition of creativity

- Stein, M. I. (1953). Creativity and culture. *The Journal of Psychology*,
  36(2), 311–322. https://doi.org/10.1080/00223980.1953.9712897
- Runco, M. A., & Jaeger, G. J. (2012). The standard definition of
  creativity. *Creativity Research Journal*, 24(1), 92–96.
  https://doi.org/10.1080/10400419.2012.650092

Novel × appropriate, the source of the value × obviousness plane.
[design spec:43](docs/specs/2026-06-12-spitballing-boundary-sampling-design.md)

### Ablation instruments (retired)

- Amabile, T. M. (1982). Social psychology of creativity: A consensual
  assessment technique. *Journal of Personality and Social Psychology*,
  43(5), 997–1013. https://doi.org/10.1037/0022-3514.43.5.997

  The CAT design behind the blind crowd-rating HITs.
  [`attic/ablation/build_hits.py:5`](attic/ablation/build_hits.py)

- Guilford, J. P., Christensen, P. R., Merrifield, P. R., & Wilson, R. C.
  (1960). *Alternate Uses: Manual*. Sheridan Supply Co.

  The brick task. The repo calls it "Alternative Uses Task"; the manual's
  title is *Alternate Uses*.
  [`docs/ablation/phase1-brick-findings.md:7`](docs/ablation/phase1-brick-findings.md)

- Krippendorff, K. (2004). *Content Analysis: An Introduction to Its
  Methodology* (2nd ed.). Sage.

  Interval-level α (ch. 11) and the 0.667 reliability floor.
  [`attic/ablation/reliability.py:7`](attic/ablation/reliability.py),
  [`docs/ablation/preregistration.md:161`](docs/ablation/preregistration.md)

- Hedges, L. V. (1981). Distribution theory for Glass's estimator of effect
  size and related estimators. *Journal of Educational Statistics*, 6(2),
  107–128. https://doi.org/10.3102/10769986006002107

  Hedges' g for the within-block contrasts.
  [`docs/ablation/preregistration.md:240`](docs/ablation/preregistration.md)

## Related work, not cited

### Originality as response frequency

The panel's obviousness measure is the classical infrequency score, inverted
and thresholded: a cluster is obvious iff ≥25% of panelists produce it.

- Wallach, M. A., & Kogan, N. (1965). *Modes of Thinking in Young Children:
  A Study of the Creativity–Intelligence Distinction*. Holt, Rinehart &
  Winston.

  Uniqueness scoring: a response counts as original iff no one else in the
  sample gave it. Same statistic as the 25% cutoff at the opposite tail.

- Silvia, P. J., Winterstein, B. P., Willse, J. T., Barona, C. M., Cram,
  J. T., Hess, K. I., Martinez, J. L., & Richard, C. A. (2008). Assessing
  creativity with divergent thinking tasks: Exploring the reliability and
  validity of new subjective scoring methods. *Psychology of Aesthetics,
  Creativity, and the Arts*, 2(2), 68–85.
  https://doi.org/10.1037/1931-3896.2.2.68

  Reviews the "well-known problems" of points-for-infrequency scoring and
  replaces it with subjective ratings. Any infrequency score is relative to
  the sample; at N=12 ([`SKILL.md:38`](skills/spitballing/SKILL.md)), one
  panelist moves a cluster 8.3 points.

- Mednick, S. A. (1962). The associative basis of the creative process.
  *Psychological Review*, 69(3), 220–232. https://doi.org/10.1037/h0048850

  Obvious answers as the dominant associates in a steep associative
  hierarchy. The panel maps the top of that hierarchy.

- Ward, T. B. (1994). Structured imagination: The role of category
  structure in exemplar generation. *Cognitive Psychology*, 27(1), 1–40.

  Imagined novel exemplars (creatures from other planets) keep the typical
  attributes of known category members. The obvious set measures that pull.

### Fixation from shown examples

- Jansson, D. G., & Smith, S. M. (1991). Design fixation. *Design Studies*,
  12(1), 3–11. https://doi.org/10.1016/0142-694X(91)90003-F
- Smith, S. M., Ward, T. B., & Schumacher, J. S. (1993). Constraining
  effects of examples in a creative generation task. *Memory & Cognition*,
  21(6), 837–845. https://doi.org/10.3758/BF03202751

Exposure to examples makes generated ideas conform to the examples'
features. SAMPLE shows generators the positive set as "taken: go outside
them" ([`SKILL.md:119`](skills/spitballing/SKILL.md)); the CONVERGE
membership test catches whole-cluster reuse, not feature-level conformity.
Whether the effect holds for LLM generators is unverified here.

### Search: blind variation vs. targeted novelty

- Campbell, D. T. (1960). Blind variation and selective retention in
  creative thought as in other knowledge processes. *Psychological Review*,
  67(6), 380–400.

  The superseded idea-funnel was BVSR: random seeds, then pruning.
  Boundary sampling replaces blind variation with variation aimed by a map.
  [design spec:5](docs/specs/2026-06-12-spitballing-boundary-sampling-design.md)

- Lehman, J., & Stanley, K. O. (2011). Abandoning objectives: Evolution
  through the search for novelty alone. *Evolutionary Computation*, 19(2),
  189–223. https://doi.org/10.1162/EVCO_a_00025

  Novelty search rewards distance from an archive of what has been found;
  the panel map plays the archive. Novelty search drops the objective;
  spitballing keeps value as a hard floor
  ([`tools/spitball/band.py:22`](tools/spitball/band.py)).

- Mouret, J.-B., & Clune, J. (2015). Illuminating search spaces by mapping
  elites. arXiv:1504.04909.
- Pugh, J. K., Soros, L. B., & Stanley, K. O. (2016). Quality diversity: A
  new frontier for evolutionary computation. *Frontiers in Robotics and AI*,
  3, 40. https://doi.org/10.3389/frobt.2016.00040

  Quality-diversity: return a set that is both good and spread out. The
  unimplemented `spread` term is this problem; MAP-Elites' one-elite-per-cell
  archive is one existing answer.
  [design spec:180](docs/specs/2026-06-12-spitballing-boundary-sampling-design.md)

### LLM homogeneity: what a model panel measures

- Jiang, L., Chai, Y., Li, M., Liu, M., Fok, R., Dziri, N., Tsvetkov, Y.,
  Sap, M., & Choi, Y. (2025). Artificial Hivemind: The open-ended
  homogeneity of language models (and beyond). *NeurIPS 2025 Datasets and
  Benchmarks Track*. arXiv:2510.22954.

  Intra-model repetition and inter-model homogeneity on open-ended prompts.
  The panel runs N=12 on the session's model
  ([`SKILL.md:49`](skills/spitballing/SKILL.md)), so its members are
  correlated: the 25% cutoff measures what this model finds obvious, not
  what a population of people would.

- Zhang, J., Yu, S., Chong, D., Sicilia, A., Tomz, M. R., Manning, C. D., &
  Shi, W. (2025). Verbalized sampling: How to mitigate mode collapse and
  unlock LLM diversity. arXiv:2510.01171.

  Attributes mode collapse to typicality bias in preference data, and
  recovers diversity by prompting for a distribution over responses. A
  prompting-only alternative to the map-then-steer approach, and an account
  of why first instincts converge.

- Argyle, L. P., Busby, E. C., Fulda, N., Gubler, J. R., Rytting, C., &
  Wingate, D. (2023). Out of one, many: Using language models to simulate
  human samples. *Political Analysis*, 31(3), 337–351.
  https://doi.org/10.1017/pan.2023.2

  "Algorithmic fidelity": conditioned LLMs reproduce human subgroup response
  distributions. The premise of population-simulated obviousness
  ([design spec:246](docs/specs/2026-06-12-spitballing-boundary-sampling-design.md));
  the panel uses no demographic conditioning.

- Doshi, A. R., & Hauser, O. P. (2024). Generative AI enhances individual
  creativity but reduces the collective diversity of novel content.
  *Science Advances*, 10(28), eadn5290.
  https://doi.org/10.1126/sciadv.adn5290
- Anderson, B. R., Shah, J. H., & Kreminski, M. (2024). Homogenization
  effects of large language models on human creative ideation. In *C&C '24:
  Creativity and Cognition*. ACM. https://doi.org/10.1145/3635636.3656204

  LLM-assisted stories were rated more creative individually but were more
  alike collectively (Doshi & Hauser); LLM-assisted ideas were more alike
  across users (Anderson et al.). The problem spitballing is aimed at.

### LLMs as judges

- Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., et
  al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena.
  *NeurIPS 2023 Datasets and Benchmarks Track*. arXiv:2306.05685.

  LLM-judge agreement with humans, and its biases (position, verbosity,
  self-enhancement). The value judge is inline, not a separate rater
  ([`SKILL.md:33`](skills/spitballing/SKILL.md)).

- Panickssery, A., Bowman, S. R., & Feng, S. (2024). LLM evaluators
  recognize and favor their own generations. *Advances in Neural
  Information Processing Systems*, 37.

  Self-preference bias. Value scores come from the model that generated the
  candidates ([`docs/spitball/pantry-dinner/result.md:12`](docs/spitball/pantry-dinner/result.md)),
  which is why that run carries a human cook test.

- Organisciak, P., Acar, S., Dumas, D., & Berthiaume, K. (2023). Beyond
  semantic distance: Automated scoring of divergent thinking greatly
  improves with large language models. *Thinking Skills and Creativity*,
  49, 101356. https://doi.org/10.1016/j.tsc.2023.101356

  Fine-tuned LLMs score AUT originality at up to r = 0.81 with human
  raters; zero- and few-shot prompting is also compared. Bears on the
  synthetic raters the ablation validated against
  ([README](README.md#ablation-study-retired)).

- Si, C., Yang, D., & Hashimoto, T. (2025). Can LLMs generate novel
  research ideas? A large-scale human study with 100+ NLP researchers.
  *ICLR 2025*. arXiv:2409.04109.

  Expert raters judged LLM ideas more novel than human ones; the same study
  reports low diversity across many LLM generations and unreliable LLM
  self-evaluation.
