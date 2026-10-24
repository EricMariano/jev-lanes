"""The replay in benchmarks/banking77/gate_report.py decides what the evaluation concludes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "banking77"))

from gate_report import decide, harm_matched_baseline, paired_bootstrap, score  # noqa: E402


def row(id, route, jev_route, conf):
    return {"id": id, "route": route, "jev_route": jev_route, "jev_confidence": conf}


def clar(id, r1, c1, r2=None, c2=None):
    r2 = r2 or r1
    c2 = c1 if c2 is None else c2
    return {
        "id": id,
        "r1_route": r1,
        "r1_confidence": c1,
        "r2_route": r2,
        "r2_confidence": c2,
    }


class TestDecide:
    def test_a_confident_first_answer_acts_without_questions(self):
        assert decide(row("a", "cards", "cards", 0.99), None, 0.9, 2) == ("cards", 0)

    def test_equality_with_the_threshold_acts(self):
        assert decide(row("a", "cards", "cards", 0.9), None, 0.9, 0) == ("cards", 0)

    def test_without_questions_a_low_confidence_case_is_declined(self):
        c = clar("a", "cards", 0.99)
        assert decide(row("a", "cards", "cards", 0.5), c, 0.9, 0) == (None, 0)

    def test_the_first_question_can_settle_it(self):
        c = clar("a", "payments", 0.95, "payments", 0.99)
        assert decide(row("a", "payments", "cards", 0.5), c, 0.9, 2) == ("payments", 1)

    def test_the_second_question_is_asked_only_if_the_first_was_not_enough(self):
        c = clar("a", "payments", 0.6, "payments", 0.95)
        assert decide(row("a", "payments", "cards", 0.5), c, 0.9, 1) == (None, 1)
        assert decide(row("a", "payments", "cards", 0.5), c, 0.9, 2) == ("payments", 2)

    def test_the_route_acted_on_is_the_one_from_the_answering_round(self):
        c = clar("a", "payments", 0.95)
        assert decide(row("a", "cards", "cards", 0.5), c, 0.9, 2)[0] == "payments"

    def test_still_unsure_after_all_questions_declines_and_counts_them(self):
        c = clar("a", "cards", 0.6, "cards", 0.7)
        assert decide(row("a", "cards", "cards", 0.5), c, 0.9, 2) == (None, 2)


class TestScore:
    ROWS = [
        row("ok", "cards", "cards", 1.0),  # right, confident
        row("wrong", "cards", "payments", 0.99),  # wrong, confident
        row("fixed", "cards", "payments", 0.4),  # wrong at first, right after a question
        row("held", None, "cards", 0.97),  # unsupported, confident
        row("held_low", None, "cards", 0.3),  # unsupported, unsure; the question does not help
    ]
    CLARS = {
        "fixed": clar("fixed", "cards", 0.96),
        "held_low": clar("held_low", "cards", 0.4, "cards", 0.5),
    }

    def test_always_act_does_whatever_jev_says(self):
        s = score(self.ROWS, self.CLARS, 0.0, 0)
        assert (s["acted"], s["correct"], s["wrong"], s["unsupported"]) == (5, 1, 2, 2)

    def test_gate_without_questions_declines_the_unsure_ones(self):
        s = score(self.ROWS, self.CLARS, 0.95, 0)
        assert (s["correct"], s["wrong"], s["unsupported"]) == (1, 1, 1)
        assert (s["declined_in"], s["declined_out"]) == (1, 1)
        assert s["questions"] == 0

    def test_questions_turn_a_decline_into_a_right_action(self):
        s = score(self.ROWS, self.CLARS, 0.95, 2)
        assert (s["correct"], s["harm"]) == (2, 2)
        assert (s["declined_in"], s["declined_out"]) == (0, 1)
        assert (s["asked"], s["questions"]) == (2, 3)
        assert (s["late_acts"], s["late_correct"]) == (1, 1)

    def test_every_case_ends_acted_or_declined(self):
        for rounds in (0, 1, 2):
            s = score(self.ROWS, self.CLARS, 0.95, rounds)
            assert s["acted"] + s["declined_in"] + s["declined_out"] == s["n"]
            assert s["correct"] + s["wrong"] + s["unsupported"] == s["acted"]


class TestControl:
    ROWS = TestScore.ROWS
    CLARS = TestScore.CLARS

    def test_harm_matched_baseline_picks_the_best_plain_gate_within_budget(self):
        rows = [
            row("a", "cards", "cards", 1.0),
            row("b", "cards", "cards", 0.8),
            row("c", None, "cards", 0.7),  # acting here is harmful
            row("d", "cards", "cards", 0.5),
        ]
        # served/harm by threshold: 1.0 -> 1/0, 0.8 -> 2/0, 0.7 -> 2/1, 0.5 -> 3/1
        assert harm_matched_baseline(rows, {}, 0) == 0.8
        assert harm_matched_baseline(rows, {}, 1) == 0.5

    def test_ties_go_to_the_higher_threshold(self):
        rows = [row("a", "cards", "cards", 1.0), row("b", "cards", "payments", 0.5)]
        assert harm_matched_baseline(rows, {}, 5) == 1.0

    def test_an_unreachable_budget_falls_back_to_the_strictest_gate(self):
        rows = [row("w", "cards", "payments", 1.0)]
        assert harm_matched_baseline(rows, {}, 0) == 1.0

    def test_bootstrap_of_identical_policies_is_zero(self):
        ci = paired_bootstrap(self.ROWS, self.CLARS, (0.95, 2), (0.95, 2), draws=50)
        assert ci["served"] == (0, 0, 0) and ci["harm"] == (0, 0, 0)

    def test_bootstrap_reports_the_observed_difference(self):
        ci = paired_bootstrap(self.ROWS, self.CLARS, (0.95, 2), (0.95, 0), draws=200)
        assert ci["served"][0] == 1  # the question serves one more customer
        assert ci["served"][1] <= ci["served"][0] <= ci["served"][2]
