"""Frozen experiment design for the Banking77 evaluation.

Fixed BEFORE any model was run on this data. Changing routes, descriptions, held-out
intents or the selection rule afterwards invalidates comparisons with earlier results.

Banking77 (PolyAI, CC BY 4.0) has 77 fine-grained banking intents. We group 66 of them into
four routes and hold out 11 intents that this imaginary support desk does not handle. For
a held-out message there is no correct route: the right outcome is human review. Several
held-out intents sit next to in-scope ones (for example wrong-exchange-rate payments next to
payment disputes), so they are a hard test for the human lane. There is deliberately no
catch-all `other` route (see docs: a catch-all absorbs vague input at confidence 1.0).
"""

from __future__ import annotations

SEED = 20261020
TARGET_AUTO_ACCURACY = 0.95  # selection rule target, see report.py

ROUTES = {
    "cards": (
        "Physical and virtual cards: ordering, delivery, activation, PIN, lost, stolen or "
        "compromised cards, cards that do not work, card expiry, and wallets such as Apple Pay."
    ),
    "payments": (
        "Card payments and cash withdrawals: declined, pending or unrecognised payments, "
        "extra or duplicate charges, wrong cash amounts, and refunds."
    ),
    "transfers": (
        "Bank transfers and top-ups: sending, receiving or cancelling transfers, failed or "
        "pending transfers, transfer fees and timing, and topping up the account by card, "
        "bank transfer or cash."
    ),
    "account": (
        "The customer's account and identity: personal details, closing the account, "
        "passcode, identity and source-of-funds verification, and a lost phone."
    ),
}

INTENTS_BY_ROUTE = {
    "cards": [
        "activate_my_card",
        "apple_pay_or_google_pay",
        "atm_support",
        "card_about_to_expire",
        "card_arrival",
        "card_delivery_estimate",
        "card_linking",
        "card_not_working",
        "card_swallowed",
        "change_pin",
        "compromised_card",
        "contactless_not_working",
        "disposable_card_limits",
        "get_disposable_virtual_card",
        "get_physical_card",
        "getting_spare_card",
        "getting_virtual_card",
        "lost_or_stolen_card",
        "order_physical_card",
        "pin_blocked",
        "virtual_card_not_working",
    ],
    "payments": [
        "Refund_not_showing_up",
        "card_payment_fee_charged",
        "card_payment_not_recognised",
        "cash_withdrawal_charge",
        "cash_withdrawal_not_recognised",
        "declined_card_payment",
        "declined_cash_withdrawal",
        "direct_debit_payment_not_recognised",
        "extra_charge_on_statement",
        "pending_card_payment",
        "pending_cash_withdrawal",
        "request_refund",
        "reverted_card_payment?",
        "transaction_charged_twice",
        "wrong_amount_of_cash_received",
    ],
    "transfers": [
        "automatic_top_up",
        "balance_not_updated_after_bank_transfer",
        "balance_not_updated_after_cheque_or_cash_deposit",
        "beneficiary_not_allowed",
        "cancel_transfer",
        "declined_transfer",
        "failed_transfer",
        "pending_top_up",
        "pending_transfer",
        "receiving_money",
        "top_up_by_bank_transfer_charge",
        "top_up_by_card_charge",
        "top_up_by_cash_or_cheque",
        "top_up_failed",
        "top_up_limits",
        "top_up_reverted",
        "topping_up_by_card",
        "transfer_fee_charged",
        "transfer_into_account",
        "transfer_not_received_by_recipient",
        "transfer_timing",
        "verify_top_up",
    ],
    "account": [
        "edit_personal_details",
        "lost_or_stolen_phone",
        "passcode_forgotten",
        "terminate_account",
        "unable_to_verify_identity",
        "verify_my_identity",
        "verify_source_of_funds",
        "why_verify_identity",
    ],
}

# Not handled by this desk: currency exchange and general product information.
HELD_OUT = [
    "age_limit",
    "card_acceptance",
    "card_payment_wrong_exchange_rate",
    "country_support",
    "exchange_charge",
    "exchange_rate",
    "exchange_via_app",
    "fiat_currency_support",
    "supported_cards_and_currencies",
    "visa_or_mastercard",
    "wrong_exchange_rate_for_cash_withdrawal",
]

INTENT_TO_ROUTE = {i: r for r, intents in INTENTS_BY_ROUTE.items() for i in intents}

assert set(ROUTES) == set(INTENTS_BY_ROUTE)
assert len(INTENT_TO_ROUTE) == sum(map(len, INTENTS_BY_ROUTE.values())), "intent in two routes"
assert not set(INTENT_TO_ROUTE) & set(HELD_OUT), "held-out intent is also routed"
assert len(INTENT_TO_ROUTE) + len(HELD_OUT) == 77
