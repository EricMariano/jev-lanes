# Banking77 evaluation

Public data (Banking77, PolyAI, CC BY 4.0), labels by the dataset's authors, routes and held-out intents fixed in `config.py` before any run. English only. **Read the limitations at the end before quoting any number.**

## Setup

- Date: 2026-10-20; seed 20261020; fallback `openai:gpt-5-nano`; TypeSafe model `jev-latest`; langchain-typesafe 0.0.1a3; jev-lanes 0.1.0rc1.
- Calibration: 231 cases from the train file (3 per intent); test: 770 cases from the test file (10 per intent). Provider failures excluded: 0 calibration, 0 test (counted as operational errors, not escalations).
- Test mix: 660 in-scope, 110 held-out (no correct route; the right outcome is human review).
- Routes: `cards`, `payments`, `transfers`, `account`; no catch-all route.
- Selection rule (frozen): highest automatic coverage on the calibration set with automatic accuracy ≥ 95%; a held-out message routed automatically counts as an error.
- Human reviews are not simulated: escalated cases are reported as escalated.

## Single-model baselines (test)

- Jev alone, in-scope accuracy: 92.1% (608/660; 95% CI 89.8–93.9%). It always names a route, so all 110 held-out messages would be routed.
- Fallback alone, in-scope accuracy (abstentions count as misses): 91.5% (604/660; 95% CI 89.1–93.4%).
- Fallback abstentions: 2.7% (21/770; 95% CI 1.8–4.1%); unknown routes: 0. On held-out messages it abstained on 18.2% (20/110; 95% CI 12.1–26.4%).

## Does Jev's confidence separate right from wrong? (test)

| Group | n | median | share ≥ 0.95 |
|---|---|---|---|
| in-scope, correct | 608 | 1.00 | 85% |
| in-scope, wrong | 52 | 0.78 | 17% |
| held-out | 110 | 0.72 | 36% |

- AUROC, correct vs wrong among in-scope: 0.884.
- AUROC, in-scope correct vs held-out: 0.818.
- 0.5 means confidence tells nothing; 1.0 means it separates perfectly.

## Thresholds chosen on calibration

- Three lanes: auto ≥ 0.95, llm ≥ 0.9. On calibration: coverage 73.2%, automatic accuracy 91.1% — target NOT reached.
- Two lanes (Jev + human, no fallback): auto ≥ 0.995. On calibration: coverage 59.7%, automatic accuracy 93.5% — target NOT reached.

## Test results at the chosen thresholds

| Configuration | Automated | Accuracy of automated | Wrong route | Held-out routed | Escalated in-scope / held-out | Fallback calls | Fallback cost |
|---|---|---|---|---|---|---|---|
| Jev alone, no escalation | 100.0% (770/770; 95% CI 99.5–100.0%) | 79.0% (608/770; 95% CI 75.9–81.7%) | 52 | 110 | 0 / 0 | 0 | n/a |
| Jev + human (auto ≥ 0.995) | 57.5% (443/770; 95% CI 54.0–61.0%) | 94.4% (418/443; 95% CI 91.8–96.1%) | 4 | 21 | 238 / 89 | 0 | n/a |
| Three lanes (auto ≥ 0.95, llm ≥ 0.9) | 77.4% (596/770; 95% CI 74.3–80.2%) | 90.6% (540/596; 95% CI 88.0–92.7%) | 16 | 40 | 104 / 70 | 31 | $0.0032 |

The fallback is called only for cases in the llm lane; its recorded answer is used. Abstentions and unknown routes escalate.

## Descriptive sweep on the test set (not used for selection)

| Jev + human, auto ≥ | Automated | Accuracy of automated | Held-out routed |
|---|---|---|---|
| 0.5 | 95.2% | 81.7% (599/733; 95% CI 78.8–84.3%) | 89/110 |
| 0.6 | 90.1% | 84.7% (588/694; 95% CI 81.9–87.2%) | 70/110 |
| 0.7 | 86.6% | 86.7% (578/667; 95% CI 83.9–89.0%) | 59/110 |
| 0.8 | 83.1% | 88.6% (567/640; 95% CI 85.9–90.8%) | 48/110 |
| 0.9 | 77.5% | 90.8% (542/597; 95% CI 88.2–92.9%) | 41/110 |
| 0.95 | 73.5% | 91.3% (517/566; 95% CI 88.7–93.4%) | 40/110 |
| 0.98 | 65.7% | 93.5% (473/506; 95% CI 91.0–95.3%) | 27/110 |
| 0.99 | 65.7% | 93.5% (473/506; 95% CI 91.0–95.3%) | 27/110 |
| 0.995 | 57.5% | 94.4% (418/443; 95% CI 91.8–96.1%) | 21/110 |
| 1.0 | 57.5% | 94.4% (418/443; 95% CI 91.8–96.1%) | 21/110 |

## Cost and latency

- Fallback tokens over all 770 test calls: 168362 in, 153909 out (145920 of them reasoning). At $0.05/$0.4 per 1M tokens: $0.0700.
- TypeSafe tokens reported: 362524 in, 35661 out. TypeSafe pricing was not checked, so no TypeSafe cost is given.
- TypeSafe latency: median 0.21s, p95 0.37s (4 concurrent workers, so under mild load).
- Fallback latency: median 2.08s, p95 4.33s (4 concurrent workers, so under mild load).

## Automatic errors of the three-lane policy (test)

- `cash_withdrawal_charge` → `cards` via llm, Jev `payments` @ 0.91, wrong (true `payments`): “Is there a limit on how much I can withdraw from my account without being charged?”
- `pending_transfer` → `payments` via auto, Jev `payments` @ 1.00, wrong (true `transfers`): “I would like to know why my payment is still pending, can you help?”
- `age_limit` → `account` via auto, Jev `account` @ 0.95, held-out routed: “Is there an age minimum?”
- `visa_or_mastercard` → `cards` via auto, Jev `cards` @ 1.00, held-out routed: “Am I able to choose my card?”
- `age_limit` → `account` via auto, Jev `account` @ 1.00, held-out routed: “How young can someone be in order to open an account?”
- `age_limit` → `account` via auto, Jev `account` @ 1.00, held-out routed: “Can I open an account for a child?”
- `visa_or_mastercard` → `cards` via auto, Jev `cards` @ 0.96, held-out routed: “What do I have to do to get a Visa credit card?”
- `supported_cards_and_currencies` → `cards` via auto, Jev `cards` @ 0.96, held-out routed: “I just have one other card from the US. Is that okay?”
- `visa_or_mastercard` → `cards` via auto, Jev `cards` @ 0.97, held-out routed: “Do I get to choose between Visa and Mastercard?”
- `visa_or_mastercard` → `cards` via auto, Jev `cards` @ 0.95, held-out routed: “Can you let me know if Visa is among the card scheme assignments?”
- `transfer_fee_charged` → `payments` via auto, Jev `payments` @ 1.00, wrong (true `transfers`): “I was charged for something I didn't expect”
- `card_payment_wrong_exchange_rate` → `payments` via auto, Jev `payments` @ 0.96, held-out routed: “The rate for a currency exchange was wrong when I bought something.”
- `age_limit` → `account` via auto, Jev `account` @ 1.00, held-out routed: “Can I open a bank account for my newborn baby?”
- `receiving_money` → `cards` via llm, Jev `payments` @ 0.92, wrong (true `transfers`): “Is it possible for me to get money out in a different currency?”
- `age_limit` → `account` via auto, Jev `account` @ 1.00, held-out routed: “I am only 17. Can I make an account?”
- `supported_cards_and_currencies` → `transfers` via auto, Jev `transfers` @ 0.99, held-out routed: “Can I use any currency to add money?”
- `supported_cards_and_currencies` → `transfers` via auto, Jev `transfers` @ 1.00, held-out routed: “Can I use my American Express to add money to my account?”
- `verify_top_up` → `account` via llm, Jev `transfers` @ 0.93, wrong (true `transfers`): “Why am i to verify the top-ups?”
- `visa_or_mastercard` → `cards` via auto, Jev `cards` @ 0.97, held-out routed: “What steps must I follow to get a Visa credit card?”
- `wrong_exchange_rate_for_cash_withdrawal` → `payments` via auto, Jev `payments` @ 1.00, held-out routed: “I used an ATM in a foreign currency but the rate applied is wrong!”
- `cancel_transfer` → `payments` via auto, Jev `payments` @ 0.99, wrong (true `transfers`): “Can I change the amount I made on a payment that I made to the payment is correct.”
- `card_payment_not_recognised` → `cards` via auto, Jev `cards` @ 0.96, wrong (true `payments`): “Please put a freeze on my card,  I am worried there has been some payments on it and I don't know what for.”
- `age_limit` → `account` via auto, Jev `account` @ 1.00, held-out routed: “How young can I be to open my own account?”
- `card_payment_wrong_exchange_rate` → `payments` via auto, Jev `payments` @ 0.99, held-out routed: “The rate applied to my foreign purchase was incorrect”
- `declined_transfer` → `payments` via auto, Jev `payments` @ 0.99, wrong (true `transfers`): “I tried to buy something online yesterday but it wouldn't stop saying declined. Tried again today but same thi”
- … (list truncated at 25)

## Limitations

- Banking77 is one domain with fine-grained, partly overlapping intents; some messages ("How long will it take to arrive?") are unanswerable without context, so no model can reach 100%. Label noise is part of every number here.
- Grouping 66 intents into four routes, and choosing 11 intents as unsupported, are our design decisions. Other groupings would give other numbers.
- English only. Nothing here says how Jev or the fallback behave in Portuguese.
- One fallback model, one run, non-deterministic fallback: no repetitions, so no variance estimate. Confidence intervals cover sampling of the test cases only.
- Thresholds come from a coarse grid and a few hundred calibration cases.
- Escalated cases are not resolved: the cost and accuracy of the human step are unknown.
- Public benchmark data may overlap with what the models were trained on.
