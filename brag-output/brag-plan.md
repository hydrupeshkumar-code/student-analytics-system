# /brag plan: SAAP (Student Assessment & Analytics Platform)

## Answers
- **What is it?** A rubric-driven platform that keeps every quiz, assignment, practical, attendance record and semester-end exam in one record per student.
- **Who is it for?** Faculty, students and the exam cell at colleges that report to NAAC/NBA.
- **What sets it apart?** Rubric marks compute themselves, an ML early-warning model flags students who are likely to fail *before* the semester-end exam (using CP data only), and the NAAC/NBA CO/PO attainment report is one click.
- **Most impressive claim:** it tells you who is going to fail while there's still time to help, with plain-language reasons.
- **Visual hook:** "Who's going to fail this semester?" in big type, with "fail" in the app's critical coral.
- **Real UI to show:** the Laboratory Practical Rubric scorer (clicking levels until 43.13 / 50 appears), the Early-warning list (97% probability, High risk, reasons), and the CO/PO attainment page with its real generated PDF.
- **Tone:** `default`: punchy, clean, playful, on the app's own soft pastel look.
- **Share caption:** "SAAP tells you which students are going to fail while there's still time to help them."

## Angle
Lead with the question every faculty member asks too late. Answer it with the product: rubric scoring feeds one record per student, the model reads it before the exam, and the accreditation report falls out the other end.

## Visual identity (from `frontend/src/styles.css`)
- Background `--bg #f6f8fa` with the app's own `--wash` (mint / lavender / pink / amber radial gradients).
- Brand emerald `#22a06b` → `#2fc483`; text `#1d2433`; critical coral `#e5534b`; violet `#6e56f0`.
- Poppins 400–700 (the project's self-hosted @fontsource files).
- Real markup reused: `.brand-mark`, `.specimen` CP card, `.stamp`, `.badge`, and the `StudyIllustration` SVG, all styled by the project's own stylesheet.
- Real UI captured from the running app (local demo seed, 2× DPR): rubric modal states, early-warning rows, attainment card and the PDF the app generated.

## Storyboard (30 fps, 1920×1080, 120 BPM, so cuts land on the beat)
| # | Time | Scene | On screen | Audio |
|---|---|---|---|---|
| 1 | 0.0–3.0 | Hook | "Who's going to **fail** this semester?" builds word by word; at 1.3s "Find out before the exam." | Soft pad + plucked arp, filter opening, riser into 3.0 |
| 2 | 3.0–6.5 | Reveal | SAAP brand mark pops; "Every quiz, rubric and exam in one clear record for each student." (the product's own headline); the real CP specimen card and illustration slide in on the right | Drop: kick, bass, clap; whoosh into it |
| 3 | 6.5–10.5 | Rubric | "Click a level. **The marks add themselves.**" Real rubric modal; cursor clicks 4 levels on the beat (7.0, 7.5, 8.0, 8.5); score lands on 43.13 / 50 | Pitched clicks in key; soft pop on the score |
| 4 | 10.5–14.5 | Early warning | "Spots **at-risk** students before the exam. And says why." Real rows slide in one by one; 97% and the reasons get highlighted | Groove continues; soft swoosh per row |
| 5 | 14.5–18.0 | Attainment | "NAAC/NBA attainment report? **One click.**" Real attainment card; cursor clicks "PDF for NAAC/NBA" at 15.5; the real PDF page rises out | Click, then a three-note chime in key |
| 6 | 18.0–21.5 | Outro | Faculty / Student / Exam-cell dashboards fan out behind; SAAP mark + "Built for faculty, students and the exam cell." + repo URL | Drums drop out, final chord rings |

Total: 21.5s.

## Privacy
All names on screen (Charan Sharma, Arjun Patel, T. Neha…) come from the project's `seed-demo` synthetic data, not real students. No emails, passwords, tokens or hostnames are shown. The GitHub repo is public, so its URL appears in the outro.
