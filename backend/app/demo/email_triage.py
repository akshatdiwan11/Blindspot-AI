"""Synthetic benchmark: support-email triage classifier with planted weaknesses.

SYNTHETIC DATA generated from templates with a fixed seed. Planted patterns:
  hinglish     Hindi-English (romanised) messages are misclassified more often
  very_short   messages under ~8 words lack context and are misclassified more often
  fraud_class  true 'Fraud' messages are frequently predicted as 'Account' (low minority recall)
"""
from __future__ import annotations

import random

SEED = 7310
N_RECORDS = 700
LABELS = {"Billing": 0.28, "Technical": 0.30, "Account": 0.22, "General": 0.12, "Fraud": 0.08}
EN = {
    "Billing": ["I was charged twice for my subscription this month, please refund the extra amount.",
                "My invoice shows a higher amount than the plan I selected during signup.",
                "Can you explain the late fee added to my last bill?"],
    "Technical": ["The app crashes every time I try to upload a file larger than 10 MB.",
                  "I cannot connect to the dashboard since the update, it keeps loading forever.",
                  "Export to CSV produces an empty file even though the table has data."],
    "Account": ["Please help me change the email address linked to my account.",
                "I want to add a second admin user to our team workspace.",
                "How do I reset my password? The reset link expired."],
    "General": ["Do you have an office in Bengaluru where I can visit?",
                "Is there a student discount for your annual plan?",
                "What are your support hours during public holidays?"],
    "Fraud": ["Someone logged into my account from another country and changed my payout details.",
              "I received an email asking for my card PIN that claims to be from you, is this real?",
              "There are transactions on my account that I did not make, please freeze it."],
}
HI = {
    "Billing": ["Mera subscription do baar charge ho gaya, extra paisa refund kar do please.",
                "Bill mein late fee kyun lagi hai, maine time pe payment kiya tha."],
    "Technical": ["App baar baar crash ho raha hai jab main file upload karta hoon.",
                  "Update ke baad dashboard khul hi nahi raha, sirf loading dikh raha hai."],
    "Account": ["Mujhe apne account ka email change karna hai, kaise karun?",
                "Password reset link expire ho gaya, naya link bhejo."],
    "General": ["Aapka office Bengaluru mein hai kya? Visit karna tha.",
                "Student discount milta hai kya annual plan pe?"],
    "Fraud": ["Kisi ne mere account mein login karke payout details badal di hain.",
              "Mere account pe aise transactions hain jo maine nahi kiye, turant block karo."],
}
SHORT = {"Billing": ["refund pls", "charged twice??"], "Technical": ["app broken", "not loading"], "Account": ["change email", "reset password"],
         "General": ["office hours?", "discount?"], "Fraud": ["hacked!!", "not my transaction"]}
CHANNELS = ["Email", "Chat", "Web form"]
CONFUSE = {"Billing": "Account", "Technical": "General", "Account": "Technical", "General": "Billing", "Fraud": "Account"}


def generate(seed: int = SEED, n: int = N_RECORDS) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    labels_list, weights = zip(*LABELS.items())
    records, truth = [], []
    for i in range(1, n + 1):
        label = rng.choices(labels_list, weights)[0]
        hinglish = rng.random() < 0.15
        very_short = rng.random() < 0.12
        if very_short:
            text = rng.choice(SHORT[label])
        else:
            text = rng.choice(HI[label] if hinglish else EN[label])
            if rng.random() < 0.5:
                text += " " + rng.choice(["Thanks.", "Please reply soon.", "Order ref " + str(rng.randint(10000, 99999)) + "."])
        p_err = 0.03
        active = {"hinglish": hinglish and not very_short, "very_short": very_short, "fraud_class": label == "Fraud"}
        for k, rate in (("hinglish", 0.30), ("very_short", 0.35), ("fraud_class", 0.40)):
            if active[k]:
                p_err = 1 - (1 - p_err) * (1 - rate)
        pred, mech = label, ""
        if rng.random() < p_err:
            mech = next((k for k in ("fraud_class", "very_short", "hinglish") if active[k]), "base")
            pred = CONFUSE[label] if mech in ("fraud_class", "hinglish") or rng.random() < 0.6 else rng.choice([l for l in labels_list if l != label])
        cid = f"EM-{i:04d}"
        records.append({"ticket_id": cid, "message": text, "true_label": label, "predicted_label": pred,
                        "channel": rng.choice(CHANNELS), "customer_tier": rng.choice(["Free", "Pro", "Enterprise"]),
                        "language": "Hinglish" if hinglish else "English"})
        truth.append({"case_id": cid, **{k: int(v) for k, v in active.items()}, "error_injected": int(bool(mech)), "error_mechanism": mech})
    return records, truth


BENCHMARK = {
    "name": "Support email triage benchmark (synthetic)", "synthetic": True, "seed": SEED, "records": N_RECORDS, "task": "classification",
    "planted_patterns": [
        {"id": "hinglish", "injected_error_rate": 0.30, "expected_detection": {"feature": "language", "op": "==", "value": "Hinglish"}},
        {"id": "very_short", "injected_error_rate": 0.35, "expected_detection": {"feature": "input_length_words", "op": "<", "value": 4}},
        {"id": "fraud_class", "injected_error_rate": 0.40, "expected_detection": {"feature": "expected_label", "op": "==", "value": "fraud"}},
    ],
    "base_error_rate": 0.03,
}
