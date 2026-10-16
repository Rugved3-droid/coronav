# PAPER_DATA.md
Generated: 2026-07-07 05:28:15 | Updated: 2026-07-07 (n=25 extension + cleanup analyses)
All numbers from disk trace files via _lm_metrics() (run_biplane.py).
All primary statistical tests are **two-tailed**. 'NOT FOUND' = no file contains the value.
Pre-specified summary statistic for per-episode rot/mm: **median + Mann-Whitney** (right-skewed distribution).

---

## 1. FINAL DATASET INVENTORY

| Status | Description | n_raw | n_filt | budget | seeds | Path |
|---|---|---|---|---|---|---|
| CANONICAL | VMR0066 wire_only V1-prompt 25 eps 60 steps seeds 5001-5265 | 25 | 25 | 60 | 5001-5265 | `trace.jsonl` |
| CANONICAL | VMR0066 overlay   V1-prompt 25 eps 60 steps seeds 5001-5265 | 25 | 25 | 60 | 5001-5265 | `trace.jsonl` |
| CANONICAL | VMR0066 wire_only V2-neutral 10 eps 60 steps | 10 | 10 | 60 | 5001-5100 | `trace.jsonl` |
| CANONICAL | VMR0066 overlay   V2-neutral 10 eps 60 steps | 10 | 10 | 60 | 5001-5100 | `trace.jsonl` |
| CANONICAL | VMR0066 wire_only V3-reworded 10 eps 60 steps | 10 | 10 | 60 | 5001-5100 | `trace.jsonl` |
| CANONICAL | VMR0066 overlay   V3-reworded 10 eps (5 API-fail excluded) | 10 | 5 (5 excl) | 60 | 5001-5100 | `trace.jsonl` |
| CANONICAL | VMR0066 wire_only V4-gentle 10 eps 60 steps | 10 | 10 | 60 | 5001-5100 | `trace.jsonl` |
| CANONICAL | VMR0066 overlay   V4-gentle 10 eps 60 steps | 10 | 10 | 60 | 5001-5100 | `trace.jsonl` |
| CANONICAL | VMR0066 wire_only_mono 10 eps 120 steps seeds 2001-2100 | 10 | 10 | 120 | 2001-2100 | `trace.jsonl` |
| CANONICAL | VMR0066 overlay_mono   10 eps 120 steps seeds 2001-2100 | 10 | 10 | 120 | 2001-2100 | `trace.jsonl` |
| CANONICAL | VMR0066 wire_only_biplane 10 eps 120 steps seeds 2001-2100 | 10 | 10 | 40 | 2001-2100 | `trace.jsonl` |
| CANONICAL | VMR0066 overlay_biplane   10 eps 120 steps seeds 2001-2100 | 10 | 10 | 48 | 2001-2100 | `trace.jsonl` |
| CANONICAL | ASOCA Normal_12 wire_only 25 eps | 25 | 25 | 45 | 3001-3265 | `trace.jsonl` |
| CANONICAL | ASOCA Normal_12 overlay   25 eps | 25 | 25 | 62 | 3001-3265 | `trace.jsonl` |
| CANONICAL | ASOCA Normal_5 wire_only  25 eps | 25 | 25 | 150 | 4001-4265 | `trace.jsonl` |
| CANONICAL | ASOCA Normal_5 overlay    25 eps (2 API-fail excluded) | 25 | 23 (2 excl) | 150 | 4001-4243 | `trace.jsonl` |
| SUPERSEDED | VMR0066 biplane_vmr0066 overlay 60 steps UNMATCHED SEEDS | 10 | 10 | 60 | 2001-2100 | `trace.jsonl` |
| SUPERSEDED | VMR0066 mono_matched_seeds overlay 60 steps (budget artifact) | 10 | 10 | 60 | 2001-2100 | `trace.jsonl` |

---

## 2. PRIMARY FINDINGS — VMR0066 (V1 prompt, seeds 5001-5265, 60 steps, n=25)

### PROVENANCE STATEMENT

**Canonical primary run: `v1_current` (n=25 per arm, current/V1 prompt)**

- Source wire_only: `D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl`
- Source overlay:   `D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\overlay\trace.jsonl`
- Seeds 5001-5100: original run (2026-07-05). Seeds 5111-5265: extension appended (2026-07-07).
- All episodes have api_ok=True, parse_ok=True. Zero exclusions in either arm.
- prompt_variant='v1_current' in every trace row (authoritative identifier).

**Re: claimed n=15 stats (U=1, p=0.0001, r=0.985, two-tailed):**
The only n=15 VMR0066 runs on disk (2026-06-28 directories) used an OLD PROMPT,
had seeds 2001-2155, and produced 0/15 success in all arms. Their actual MW stats are:
U=55, p=0.018 (two-sided), r=0.511 — overlap in per-episode rot/mm prevents U=1.
**No file on disk produces U=1, p=0.0001, r=0.985. This claim is NOT FOUND IN FILES.**

---

### Finding 1: Overlay increases LM-phase rotation (n=25, LOCKED)

**Pre-specified summary: median per-episode rot/mm + Mann-Whitney U.**
Justification: wire_only distribution is strongly right-skewed (skew=3.22) due to ep15 outlier
(see Outlier note below). Median is the appropriate central tendency for rank-based inference.

| Arm | n | median rot/mm | IQR | mean rot/mm | skewness |
|---|---|---|---|---|---|
| wire_only | 25 | 0.145 | [0.134, 0.161] | 0.157 | 3.22 |
| overlay   | 25 | 0.175 | [0.158, 0.198] | 0.178 | −0.17 |

- **Mann-Whitney U=129, p=0.0004 (two-tailed), r=0.587**  (n=25 per arm)
- One-tailed (wire_only < overlay): p=0.0002
- Overlay median +21% above wire_only; mean +13% (less informative due to outlier)

**Per-episode rot/mm (all 25 episodes):**
- wire_only: [0.150, 0.196, 0.109, 0.162, 0.132, 0.145, 0.145, 0.161, 0.136, 0.146, 0.134, 0.166, 0.130, 0.152, **0.371**, 0.134, 0.145, 0.180, 0.218, 0.143, 0.157, 0.125, 0.113, 0.148, 0.139]
- overlay:   [0.171, 0.162, 0.209, 0.198, 0.222, 0.163, 0.162, 0.230, 0.152, 0.192, 0.175, 0.152, 0.153, 0.105, 0.180, 0.182, 0.148, 0.220, 0.158, 0.186, 0.170, 0.186, 0.210, 0.200, 0.158]

**OUTLIER NOTE — ep15 wire_only (seed 5155, rot/mm=0.371):**
This episode failed (no target reached). Its rot/mm=0.371 is an extreme outlier:
next-highest in wire_only is 0.218; all overlay values fall between 0.105 and 0.230.
This single episode pulls the aggregate (pooled) rot/mm to wo=0.182 > ov=0.177 —
a REVERSAL of direction on the aggregate. The aggregate is not the pre-specified
summary and should not be reported as such. The MW test on per-episode medians/ranks
is unaffected by the outlier magnitude.

**SENSITIVITY ANALYSIS — ep15 excluded (seed 5155 removed from wire_only, n_wo=24):**
- wire_only (n=24): median=0.145, mean=0.149
- MW U=104, **p=0.0001 (two-tailed), r=0.653**
- Finding STRENGTHENS without the outlier, confirming it is not driving the result.

---

### Finding 2: Overlay slows successful navigation (n=25, LOCKED)

**IMPORTANT SEPARATION: steps-to-target and success rate are distinct claims.**

#### 2a. Steps-to-target MW (all successful episodes, unmatched)

| Arm | n_success | median steps | mean steps |
|---|---|---|---|
| wire_only | 20/25 | 48.0 | 48.9 |
| overlay   | 13/25 | 58.0 | 56.0 |

- **Mann-Whitney U=24, p=0.0001 (two-tailed), r=0.812**  (n_wo=20, n_ov=13 successful eps)
- One-tailed: p=0.0001
- Note: different n (20 vs 13) means overlay's 13 successes are a selected subset (harder seeds
  may have failed). Seed-matched Wilcoxon below is the confound-free version.

#### 2b. Steps-to-target Wilcoxon signed-rank (seed-matched, CONFOUND-FREE)

Seeds where BOTH arms succeeded (n=9): 5045, 5067, 5078, 5122, 5144, 5166, 5177, 5243, 5254

| Seed | wire_only steps | overlay steps | diff (ov−wo) |
|---|---|---|---|
| 5045 | 48 | 55 | +7 |
| 5067 | 46 | 49 | +3 |
| 5078 | 46 | 56 | +10 |
| 5122 | 50 | 58 | +8 |
| 5144 | 55 | 51 | −4 |
| 5166 | 41 | 50 | +9 |
| 5177 | 55 | 58 | +3 |
| 5243 | 48 | 59 | +11 |
| 5254 | 45 | 59 | +14 |
| **mean** | **48.2** | **55.0** | **+6.8** |
| **median** | **48.0** | **56.0** | **+8.0** |

- **Wilcoxon signed-rank W=3, p=0.0195 (two-tailed), n=9**
- One-tailed (wo < ov): p=0.0098
- 8/9 seeds: overlay takes more steps. One reversal: seed 5144 (wo=55, ov=51, diff=−4).
- Conclusion: within-seed step penalty for overlay holds (p=0.0195), not a selection artifact.

#### 2c. Success rate — NOT significant (do not claim)

- wire_only: 20/25 (80%)  overlay: 13/25 (52%)
- **Fisher two-sided p=0.0718 — NOT significant at α=0.05**
- Correct framing: "a directional but non-significant reduction in success rate with overlay
  (80% vs 52%, Fisher p=0.072)." Never merge with the steps finding into a single "success" claim.

---

### Finding 3: Wrong-branch at first LM bifurcation — NULL at n=25

| Arm | first-bif LCX / n | first-bif LAD |
|---|---|---|
| wire_only | 8/25 (32%) | 17/25 |
| overlay   | 9/25 (36%) | 16/25 |

- **Fisher first-bif LCX: p=1.000 (two-sided) — NULL**
- Fisher success: p=0.0718 (same as 2c above — NS)

**n=10 result (p=0.0325, 0/10 vs 5/10 LCX) was a seed-specific artifact.**
In the original 10 seeds (5001-5100) wire_only avoided LCX entirely; overlay entered it 5/10 times.
With seeds 5111-5265, wire_only got LCX first on 8/15 new episodes; overlay on 4/15 new episodes.
The effect reverses and nulls — the n=10 finding is dropped. Wrong-branch rate is ~32-36% in
both arms at n=25 with no statistically or directionally meaningful difference.

---

## 3. CROSS-ANATOMY DISSOCIATION TABLE

### VMR0066 (V1 prompt, seeds 5001-5265, 60 steps, n=25 LOCKED)
Source: `D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl` / `D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\overlay\trace.jsonl`

| Metric | wire_only | overlay |
|---|---|---|
| n (analysed) | 25 | 25 |
| step budget | 60 | 60 |
| seeds | 5001-5265 | 5001-5265 |
| success | 20/25 | 13/25 |
| LM rot/mm median [IQR] | 0.145 [0.134, 0.161] | 0.175 [0.158, 0.198] |
| first-bif LCX | 8/25 | 9/25 |
| median steps (success) | 48.0 | 58.0 |
| any-LCX episodes | 9/25 | 11/25 |
| total LCX steps | 158 | 211 |
| MW rot/mm (two-sided) | U=129, **p=0.0004**, r=0.587 | - |
| Sensitivity excl ep15 (two-sided) | U=104, **p=0.0001**, r=0.653 | - |
| MW steps-success (two-sided) | U=24, **p=0.0001**, r=0.812 [n=20 vs 13] | - |
| Wilcoxon steps paired (two-sided) | W=3, **p=0.0195** [n=9 matched seeds] | - |
| Fisher success (two-sided) | p=0.0718 (NS) | - |
| Fisher first-bif LCX (two-sided) | p=1.000 (NS) | - |

### ASOCA Normal_12
Source: `D:\steve\pilot\runs\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl` / `D:\steve\pilot\runs\normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl`

| Metric | wire_only | overlay |
|---|---|---|
| n (analysed) | 25 | 25 |
| step budget | 45 | 62 |
| seeds | 3001-3265 | 3001-3265 |
| success | 25/25 | 25/25 |
| LM rot% | 0.0% | 7.8% |
| LM rot/mm | 0.000 | 0.050 |
| first-bif LCX | 0/25 | 0/25 |
| mean steps (success) | 41.0 | 56.0 |
| any-LCX episodes | 0/25 | 0/25 |
| total LCX steps | 0 | 0 |
| MW rot/mm (two-sided) | U=112, **p=0.0000**, r=0.640 | - |
| Fisher success (two-sided) | **p=1.0000** | - |
| Fisher first-bif LCX (two-sided) | **p=1.0000** | - |

### ASOCA Normal_5
Source: `D:\steve\pilot\runs\normal5_wire_only\arm_asoca_normal5_wire_only\trace.jsonl` / `D:\steve\pilot\runs\normal5_overlay\arm_asoca_normal5_overlay\trace.jsonl`

| Metric | wire_only | overlay |
|---|---|---|
| n (analysed) | 25 | 23 (2 excl) |
| step budget | 150 | 150 |
| seeds | 4001-4265 | 4001-4243 |
| success | 10/25 | 0/23 |
| LM rot% | 48.7% | 72.6% |
| LM rot/mm | 0.151 | 0.246 |
| first-bif LCX | 1/25 | 0/23 |
| mean steps (success) | 118.8 | nan |
| any-LCX episodes | 1/25 | 0/23 |
| total LCX steps | 1 | 0 |
| MW rot/mm (two-sided) | U=33, **p=0.0000**, r=0.885 | - |
| Fisher success (two-sided) | **p=0.0007** | - |
| Fisher first-bif LCX (two-sided) | **p=1.0000** | - |

### ASOCA Normal_5 overlay distance distribution
- n analysed: 23 (2 excl — see DATA-EXCLUSIONS)
- Successes: 0/23
- Mean final dist: **37.3 mm** (SD 1.9)
- Mean min dist:   **36.0 mm** (SD 1.3)
- All min-dists (sorted): ['33.4', '34.2', '35.2', '35.2', '35.2', '35.2', '35.2', '35.2', '35.2', '35.4', '35.6', '35.6', '35.9', '35.9', '36.2', '36.7', '37.1', '37.3', '37.5', '37.7', '37.8', '37.9', '38.6']

---

## 4. PROMPT-ROBUSTNESS ABLATION — VMR0066

**CLAIM CORRECTION (2026-07-09): The robustness evidence for the overlay effect is the**
**cross-anatomy replication (A1/A2/A3 all p<0.001), NOT the prompt ablation.**
**The prompt ablation is an underpowered secondary check (n=10 per variant).**
**Do NOT write "effect persists under neutral prompt V2" — V2 is uninformative (see below).**

Source: `D:\steve\pilot\runs/ablation_prompt_robustness/` — all values from `_lm_metrics()`, two-sided Mann-Whitney.

| Variant | Arm | n | med rot/mm | mean rot/mm | nonzero | MW two-sided p | r | Status |
|---|---|---|---|---|---|---|---|---|
| V1 current | wire_only | 25 | 0.145 | 0.158 | 25/25 | — | — | — |
| V1 current | overlay | 25 | 0.175 | 0.178 | 25/25 | **p=0.0004** | 0.587 | **SIGNIFICANT** |
| V2 neutral | wire_only | 10 | 0.000 | 0.000 | 0/10 | — | — | — |
| V2 neutral | overlay | 10 | 0.000 | 0.015 | 2/10 | p=0.168 | 0.200 | UNINFORMATIVE |
| V3 reworded | wire_only | 10 | 0.097 | 0.097 | 10/10 | — | — | — |
| V3 reworded | overlay | 10* | 0.043 | 0.051 | 5/10 | p=0.138 | −0.400 | EXCLUDED |
| V4 gentle | wire_only | 10 | 0.140 | 0.138 | 10/10 | — | — | — |
| V4 gentle | overlay | 10 | 0.148 | 0.144 | 10/10 | p=0.241 | 0.320 | same direction, NS |

*V3 overlay n=10 per _lm_metrics; 5 of 10 episodes had all rows api_ok=False (contribute 0.0). See DATA-EXCLUSIONS.

**Per-variant sign and interpretation (locked):**

| Variant | ov − wo median | Sign | p | Interpretation |
|---|---|---|---|---|
| V1 (n=25) | +0.030 | **+** | **p=0.0004** | SIGNIFICANT — primary finding |
| V2 (n=10) | 0.000 (tied) | tied | p=0.168 | UNINFORMATIVE: V2 prompt suppresses rotation in both arms (0/10 wire_only nonzero; 2/10 overlay nonzero). Both medians = 0.000. V2 overlay mean slightly higher (0.015 vs 0.000) but the comparison is effectively flat. Cannot claim "effect persists under neutral prompt." |
| V3 (n=10) | −0.054 | **−** (reversed) | p=0.138 | EXCLUDED: nav. collapsed (0/10 success both arms); reversed sign. |
| V4 (n=10) | +0.008 | **+** | p=0.241 | Same direction as V1, underpowered. Both arms fully nonzero (10/10). |

**Power note:** An effect of r=0.587 (V1) requires n≈16 per arm for 80% power at α=0.05. The n=10 per-variant ablation is underpowered by design. Non-significance in V2/V4 does not mean no effect; it means the ablation cannot resolve it.

**HONEST ROBUSTNESS CLAIM (use this text):**
> The overlay effect on LM rotation is established in the primary condition (V1, n=25 per arm, p=0.0004, r=0.587). Prompt ablation variants with n=10 are individually underpowered. Of the three functional variants: V4 (gently rephrased, n=10) shows the same direction as V1 (ov median +0.8% above wire_only, p=0.241); V2 (bare-minimum neutral, n=10) is uninformative — both arms produce near-zero rotation (8–10/10 episodes have lm_rot_mm=0), so no comparison can be made; V3 (aggressively reworded) causes navigation collapse (0/10 success both arms) and is excluded. **Primary robustness evidence is the cross-anatomy replication across three anatomies and two CT data sources (A1 p=0.0004, A2 p=0.000003, A3 p=0.000009; all p<0.001), not the prompt ablation.**

**ABSTRACT CORRECTION (2026-07-09):**
REMOVE: "...and persists under a no-scaffold neutral prompt (V2)."
REPLACE WITH: "...and replicates across all three anatomies and both CT data sources (all p<0.001)."
Rationale: V2 is uninformative (rotation suppressed in both arms); the cross-anatomy result is the true robustness evidence.

---

## 5. BIPLANE FINAL RESULT -- 120-step seed-matched 4-arm

Source files:
- `D:\steve\pilot\runs\mono_120steps\arm_coronary_wire_only\trace.jsonl`
- `D:\steve\pilot\runs\mono_120steps\arm_coronary_overlay\trace.jsonl`
- `D:\steve\pilot\runs\biplane_120steps\wire_only\trace.jsonl`
- `D:\steve\pilot\runs\biplane_120steps\overlay\trace.jsonl`

| Arm | n | Budget | LM rot% | rot/mm | first-bif LCX | any-LCX eps | LCX steps | Success | mean steps |
|---|---|---|---|---|---|---|---|---|---|
| wire_only_mono | 10 | 120 | 24.8% | 0.299 | 6/10 | 7/10 | 251 | 6/10 | 80.0 |
| wire_only_biplane | 10 | 120 | 23.1% | 0.172 | 4/10 | 4/10 | 27 | 8/10 | 36.5 |
| overlay_mono | 10 | 120 | 27.1% | 0.213 | 6/10 | 9/10 | 424 | 5/10 | 85.0 |
| overlay_biplane | 10 | 120 | 26.5% | 0.154 | 5/10 | 5/10 | 28 | 9/10 | 43.1 |

**Statistical tests (two-sided):**
- wire_only rot/mm MW: U=53, **p=0.8501**, r=-0.060
- wire_only success Fisher: **p=0.6285** [6/10 vs 8/10]
- wire_only first-bif LCX Fisher: **p=0.6563** [6/10 vs 4/10]
- overlay rot/mm MW: U=39, **p=0.4274**, r=0.220
- overlay success Fisher: **p=0.1409** [5/10 vs 9/10]
- overlay first-bif LCX Fisher: **p=1.0000** [6/10 vs 5/10]

**Correction cascade (overlay LM-rot% biplane - monoplane):**
- Stage 1: unmatched seeds 60 steps: bi=25.1% - mono=31.5% = **-6.3 pp** (seeds 2001-2100 vs 5001-5100)
- Stage 2: seed-matched 60 steps: bi=25.1% - mono=27.4% = **-2.2 pp** (matched seeds, budget artifact)
- Stage 3: seed-matched 120 steps (FINAL): bi=26.5% - mono=27.1% = **-0.6 pp** (fair comparison)

**Step efficiency -- shared-success seeds (120-step arms):**
- wire_only (n=4 shared seeds [2023, 2034, 2067, 2100]):
  - mono steps: [80, 79, 83, 79]  mean=80.2
  - bi   steps: [35, 37, 35, 37]  mean=36.0
  - diff (bi-mono): [-45, -42, -48, -42]  mean=-44.2
- overlay (n=5 shared seeds [2001, 2023, 2056, 2067, 2100]):
  - mono steps: [81, 90, 84, 83, 87]  mean=85.0
  - bi   steps: [40, 44, 47, 44, 41]  mean=43.2
  - diff (bi-mono): [-41, -46, -37, -39, -46]  mean=-41.8

---

## 6. CROSS-ANATOMY LM-ILLUSION AND OVERLAY EFFECT — LOCKED

**Source: `lm_illusion_compare.json` (scripted traversal, 3 seeds per anatomy) + VLM trace files.**
**Computation: `_lm_illusion_locked.py` run 2026-07-09.**

### 6a. LM-phase-ONLY illusion metric

**Method:** max(d\_tgt during LM-labeled steps) − d\_tgt[step 1].
LM phase = steps where tip\_branch\_obs == 'left\_main' (same field as `_lm_metrics`).
Post-bifurcation steps excluded from rise computation.

| Anatomy | LM-phase peak rise | Illusion (>1mm) | Note |
|---|---|---|---|
| A1 VMR0066 | **+4.358mm** (mean 3 seeds, range 4.35–4.36) | **YES** | Peak at scripted step 6, b=left_main confirmed |
| A2 Normal-12 | **0.000mm** | NO | Monotone decrease from step 1; peak IS step 1 |
| A3 Normal-5 | **+0.158mm** (mean 3 seeds, range 0.12–0.18) | NO | Peak at scripted step 4; the +23.27mm is post-bif LCx divergence, NOT illusion |

**VLM-trace cross-check (wire_only, n=25 eps, peak rise during left_main steps):**
- A1: median +4.17mm, mean +5.20mm (outlier ep inflates mean) — confirms illusion
- A2: median 0.000mm — confirms no illusion
- A3: median +0.80mm, mean +0.78mm — below 1mm threshold, confirms no illusion

**The +23.27mm in A3's `rise_mm` JSON field is WRONG to report as an "LM rise."**
It is `max(full d_series) - d_start` which sweeps in steps 12–15 (all in `lcx`, wrong branch).
The scripted wire enters LCx at step 12 (post-bifurcation). That is wrong-branch divergence.

**NOTE on user-stated alternative values (+2.71mm/−0.02mm/−1.90mm):**
The value +2.71mm matches `d(last_LM_step) − d(step_1)` for A1 = +2.670mm (net exit change, not peak).
The values −0.02mm (A2) and −1.90mm (A3) cannot be reproduced from any file on disk via any formula.
Locking peak-rise values above (data-verifiable) as the canonical metric.

---

### 6b. Per-anatomy overlay effect — LOCKED

**Source: per-episode lm\_rot\_mm via `_lm_metrics()`. Two-sided Mann-Whitney U.**

| Anatomy | LM illusion | wo n | wo med | ov n | ov med | med diff | MW p | r |
|---|---|---|---|---|---|---|---|---|
| A1 VMR0066 | YES +4.36mm | 25 | 0.1452 | 25 | 0.1749 | +0.0297 (+20%) | **p=0.0004** | 0.587 |
| A2 Normal-12 | NO 0.00mm | 25 | 0.0000 | 25 | 0.0454 | +0.0454 (0→+) | **p=0.000003** | 0.640 |
| A3 Normal-5 | NO +0.18mm | 25 | 0.1473 | 23* | 0.2307 | +0.0833 (+57%) | **p=0.000009** | 0.734 |

*A3 overlay n=23 (2 API exclusions)

**Key finding: Overlay SIGNIFICANTLY increases LM rotation in ALL THREE anatomies.**
This INVALIDATES the "effect present in A1, absent in A2/A3" dissociation claim.
Effect-size ordering by anatomy: A1 (+0.030) < A2 (+0.045) < A3 (+0.083) — scales with anatomical difficulty, NOT with illusion presence.

### 6c. Correct framing of the cross-anatomy result

**What the data supports:**
1. The LM-bend illusion (d\_tgt rise during LM phase) is present ONLY in A1 (+4.36mm), absent in A2 (0.00mm) and A3 (+0.18mm below threshold).
2. Overlay increases LM rotation significantly in ALL THREE anatomies (A1 p=0.0004, A2 p=0.000003, A3 p=0.000009).
3. The behavioral consequence of the rotation increase is anatomy-gated:
   - A2 (straight, short LM → direct LAD path): rotation increase is **behaviorally inert** — success stays 25/25, first-bif LCX 0/25 both arms.
   - A1 (LM bends toward LCX at bifurcation + illusion): rotation increase is **harmful** — success 20→13/25, steps slower (MW p=0.0001).
   - A3 (LM geometry biases scripted wire toward LCX; VLM takes 150 steps): rotation increase is **catastrophic** — success 10→0/23, Fisher p=0.0007.
4. The magnitude of the rotation effect scales with anatomical difficulty (A1 < A2 < A3 by absolute diff), not with illusion presence.

**What the data does NOT support:**
- "Effect present in A1, absent in A2/A3" — FALSE (all three significant)
- "Effect tracks the illusion" — FALSE (A2 has no illusion but largest r=0.640)
- A3's +23.27mm as an "LM rise" — WRONG, it is post-bif LCx divergence

---

## DATA-EXCLUSIONS

All episodes where _lm_metrics excluded rows (api_ok=False OR parse_ok=False).
**Exclusions are NOT outcome-dependent**: failures are API errors unrelated to navigation result.

### V3 reworded overlay -- 5 of 10 episodes excluded
Source: `D:\steve\pilot\runs\ablation_prompt_robustness\v3_reworded\overlay\trace.jsonl`

| ep | Seed | good rows | bad rows | First bad step | Status | terminal |
|---|---|---|---|---|---|---|
| ep04 | 5034 | 7 | 53 | 8 | INCLUDED-PARTIAL (7 good rows, API failed from step 8) | False |
| ep05 | 5045 | 0 | 60 | 1 | EXCLUDED (all rows api_ok=False) | False |
| ep06 | 5056 | 0 | 60 | 1 | EXCLUDED (all rows api_ok=False) | False |
| ep07 | 5067 | 0 | 60 | 1 | EXCLUDED (all rows api_ok=False) | False |
| ep08 | 5078 | 0 | 60 | 1 | EXCLUDED (all rows api_ok=False) | False |
| ep09 | 5089 | 0 | 60 | 1 | EXCLUDED (all rows api_ok=False) | False |

Conclusion: eps 5-9 (seeds 5045-5089) excluded -- all 60 rows api_ok=False each.
ep4 (seed 5034) included-partial (7 good rows steps 1-7, then API failed at step 8).
n_analysed=5 (eps 1,2,3,4,10). Same seeds ran cleanly in all other ablation arms --
exclusion is clearly caused by transient API failure, not navigation outcome.

### ASOCA Normal_5 overlay -- 2 of 25 episodes excluded
Source: `D:\steve\pilot\runs\normal5_overlay\arm_asoca_normal5_overlay\trace.jsonl`

| ep | Seed | good rows | bad rows | First bad step | Status | terminal |
|---|---|---|---|---|---|---|
| ep02 | 4012 | 149 | 1 | 39 | INCLUDED-PARTIAL (1 bad row(s) -- 149 good retained) | False |
| ep08 | 4078 | 149 | 1 | 40 | INCLUDED-PARTIAL (1 bad row(s) -- 149 good retained) | False |
| ep10 | 4100 | 149 | 1 | 149 | INCLUDED-PARTIAL (1 bad row(s) -- 149 good retained) | False |
| ep23 | 4243 | 146 | 4 | 147 | INCLUDED-PARTIAL (4 bad row(s) -- 146 good retained) | False |
| ep24 | 4254 | 0 | 150 | 1 | EXCLUDED (all 150 rows api_ok=False) | False |
| ep25 | 4265 | 0 | 150 | 1 | EXCLUDED (all 150 rows api_ok=False) | False |

Conclusion: eps 24-25 (seeds 4254, 4265) excluded -- all 150 rows api_ok=False.
eps 2,8,10,23 had 1-4 bad rows each but remain INCLUDED (146-149 good rows retained).
n_analysed=23. Exclusions at end-of-run (eps 24-25 = last two episodes) are consistent
with rate-limiting, not outcome-dependent selection.

---

## 6. EXACT SIMULATION CONFIG

### 6a. Software versions
- SOFA: **v23.06.00**  (`D:\steve\deps\SOFA_v23.06.00_Win64`)
- stEVE: **v0.2**  (`D:\steve\stEVE\setup.py`)
- BeamAdapter: **branch v23.06**, commit `6ec25b6e6f8ac7b1e878cca5be27c4dffd9ae931`
  (GitHub: sofa-framework/BeamAdapter; source: `plugins\BeamAdapter\git-info.txt`)
- Python: **3.8.20**  (conda env `steve`, confirmed in all run logs)
- Anthropic Python SDK: **0.72.0**  (verified: `import anthropic; anthropic.__version__`)
- VLM model: **claude-sonnet-4-6**  (MODEL constant in `run_coronary.py`)

### 6b. VLM harness constants -- from run_coronary.py
- MODEL: `claude-sonnet-4-6`
- TRANS_LIMIT (mm): `50.0`
- ROT_LIMIT (rad): `3.14159`
- RETRACTION_BUDGET (steps): `2`
- MAX_RESET_TRIES: `3`
- XTIP_HEALTHY_MAX (mm): `10.0`
- PROXIMITY_GATE_DIST_MM: `25.0`
- PROXIMITY_GATE_ADV_DEFAULT: `35.0`
- IMAGE_SIZE (px): `512, 512`
- IMAGE_ROT_ZX (AP view): `0, -40`

### 6c. SOFA simulation parameters
From `D:\steve\stEVE\coronary_fixture\coronary_sim.py` and `sofabeamadapter.py`:

| Parameter | Value | Source |
|---|---|---|
| dt (time step) | **0.006 s** | `sofabeamadapter.py` L16: `dt_simulation: float = 0.006` |
| contact solver | FreeMotionAnimationLoop | `coronary_sim.py` L62 |
| proximity detection | LocalMinDistance | `coronary_sim.py` L66 |
| contactDistance | **0.3 mm** | `coronary_sim.py` L67 |
| alarmDistance | **0.5 mm** | `coronary_sim.py` L68 |
| constraint solver | GaussSeidel LCP | `coronary_sim.py` L78-79 |
| GaussSeidel maxIt | **2000** | `coronary_sim.py` L79 |
| GaussSeidel tolerance | **1e-4** | `coronary_sim.py` L78 |
| friction (mu) | **0.001** | `coronary_sim.py` L77 |
| wire_diameter | **0.89 mm** | `run_coronary.py` build_env() |
| tip_radius | **1.5 mm** | `run_coronary.py` build_env() |
| tip_angle | **0.2 deg** | `run_coronary.py` build_env() |
| image_frequency | **7.5 fps** | `run_coronary.py` build_env() |

### 6d. Biplane second-view config
- Second view: `[60, -20]` (LAO 60 deg, Cranial 20 deg -- clinical spider view)
- AP Cranial 40 + LAO 60 Cranial 20 is the standard clinical LCA biplane pair.
- Source: `D:\steve\pilot\render_biplane_pair.py` doc-string; `run_biplane.py`

### 6e. Authoritative metric definitions -- _lm_metrics() from run_biplane.py
```python
def _lm_metrics(rows):
    """Compute LM-phase rotation%, LM rot/mm, wrong-branch%, success, steps-to-target.
    Handles both old run_coronary schema (intended_direction, dist_delta) and
    new biplane schema (is_rotate_step, tip_target_dist_after)."""
    eps = {}
    for r in rows:
        if r.get("api_ok", True) and r.get("parse_ok", True):
            eps.setdefault(r["episode"], []).append(r)

    lm_rot_steps = lm_total_steps = 0
    lm_rot_per_mm_num = lm_dist_denom = 0.0
    wrong_br = 0; total_adv = 0
    successes = 0; steps_to_tgt = []

    for ep_rows in eps.values():
        for r in ep_rows:
            br = r.get("tip_branch_obs", "")
            # is_rotate_step: explicit field (new schema) or infer from intended_direction
            if "is_rotate_step" in r:
                is_rot = bool(r["is_rotate_step"])
            else:
                intent = r.get("intended_direction", "")
                is_rot = intent in ("rotate_cw", "rotate_ccw")

            # distance change: tip_target_dist_after (new) or dist_delta (old)
            if "tip_target_dist_after" in r:
                dist_change = abs(r["tip_target_dist_after"] - r["tip_target_dist"])
            elif "dist_delta" in r:
                dist_change = abs(r.get("dist_delta", 0.0))
            else:
                dist_change = 0.0

            if br == "left_main":
                lm_total_steps += 1
                if is_rot:
                    lm_rot_steps      += 1
                    lm_rot_per_mm_num += dist_change
                lm_dist_denom += dist_change

            intent = r.get("intended_direction", "")
            if intent.startswith("advance") or (not intent and r.get("translation", 0) > 0):
                total_adv += 1
                if br.startswith("lcx"):
                    wrong_br += 1

        if ep_rows[-1].get("terminal"):
            successes += 1
            steps_to_tgt.append(len(ep_rows))

    n_eps      = len(eps)
    lm_rot_pct = 100.0 * lm_rot_steps / lm_total_steps if lm_total_steps else 0.0
    lm_rot_mm  = lm_rot_per_mm_num / lm_dist_denom if lm_dist_denom > 0 else 0.0
    wrong_pct  = 100.0 * wrong_br / total_adv if total_adv else 0.0
    mean_steps = float(np.mean(steps_to_tgt)) if steps_to_tgt else float("nan")
    return {
        "lm_rot_pct": lm_rot_pct, "lm_rot_mm": lm_rot_mm,
        "wrong_br_pct": wrong_pct,
        "success": f"{successes}/{n_eps}",
        "mean_steps": mean_steps,
        "n_eps": n_eps,
    }


# ── Analysis: biplane vs monoplane comparison ─────────────────────────────────
```

Operational definitions:
- **LM rot%**: rotation steps in left_main / total left_main steps x 100
- **rot/mm**: sum(dist_change on rotation steps in LM) / sum(dist_change all LM steps)
  Dimensionless fraction <=1; measures what fraction of LM progress occurs while rotating
- **success**: terminal=True before step budget exhausted
- **steps-to-target**: episode row count on successful episodes only
- **first-bif wrong-branch**: first branch after exiting left_main is lcx*
- **Rotation detection**: is_rotate_step (biplane) OR intended_direction in {rotate_cw, rotate_ccw}
- **Distance change**: tip_target_dist_after-tip_target_dist (biplane) OR dist_delta (monoplane)

---

## 7. KNOWN LIMITATIONS / PROVENANCE

### Normal_5 mesh provenance (from clip_asoca_left.py L116-L250)
ASOCA Normal_5 lumen radius ~2.75 mm < clip radius 4.0 mm. Proximity clip retains
all faces, producing a CLOSED mesh. Closed mesh causes GaussSeidel LCP instability.
Resolution: SYNTHETIC OPEN TUBE generated from patient centerlines (tube_radius=2.5 mm).
The tube follows ASOCA Normal_5 centerline geometry but the SURFACE is synthetic.
Source: `D:\steve\pilot\clip_asoca_left.py` L116-L250, TUBE_RADIUS_MM=2.5

### Normal_12 mesh provenance
Normal_12 lumen radius > 4 mm -- proximity clip produces an OPEN mesh, so the actual
ASOCA lumen surface is used directly (no synthetic fallback needed).

### Other limitations
- Simulation-only: no phantom or in-vivo validation
- Single VLM family: all arms used claude-sonnet-4-6
- Small n: VMR0066 n=10 per arm; ASOCA n=25 per arm -- below conventional power thresholds
- V2 overlay/wire_only: near-zero LM rotation -- VLM took near-zero rotation steps in both arms
- V3 overlay n=5: 5 eps excluded (API failure); treat results as exploratory only

**Biplane correction cascade (effect on overlay rotation pp):**
| Correction | Delta pp |
|---|---|
| Seed confound (5001-5100 vs 2001-2100) -- re-ran mono at matched seeds | -6.3 pp -> -2.2 pp |
| Budget artifact (0/10 mono at 60 steps) -- re-ran all 4 arms at 120 steps | -2.2 pp -> -0.6 pp |
| LCX aggregate confound -- replaced with first-bifurcation metric | Fisher ns both budgets |
| Analysis bug (translation field missing from mono traces) -- fixed | Spurious 0/10 -> 9/10 |

---

## 8. REPRODUCIBILITY

Entry-point scripts:
- `D:\steve\pilot\run_ablation.py`
- `D:\steve\pilot\run_asoca.py`
- `D:\steve\pilot\run_biplane.py`
- `D:\steve\pilot\run_budget.py`
- `D:\steve\pilot\run_coronary.py`
- `D:\steve\pilot\run_full_intervention.py`
- `D:\steve\pilot\run_proximity_gate.py`
- `D:\steve\pilot\run_topology.py`
- `D:\steve\pilot\run_v4.py`

Key paths:
- stEVE: `D:\steve\stEVE\`  |  SOFA: `D:\steve\deps\SOFA_v23.06.00_Win64\`
- Conda env: `D:\conda\envs\steve\`  |  Activation: `D:\steve\activate_steve.ps1`
- Run outputs: `D:\steve\pilot\runs\`

To reproduce primary run (V1 prompt, n=10, 60 steps):
```powershell
. D:\steve\activate_steve.ps1
$env:ANTHROPIC_API_KEY = 'sk-...'
python run_coronary.py --mode wire_only --seeds 5001,5012,5023,5034,5045,5056,5067,5078,5089,5100 --steps 60
python run_coronary.py --mode overlay   --seeds 5001,5012,5023,5034,5045,5056,5067,5078,5089,5100 --steps 60
```
