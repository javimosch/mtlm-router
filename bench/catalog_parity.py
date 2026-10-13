# catalog_parity.py — parity table between the mtlm-heads catalog
# and the runtime lanes an appliance can actually serve.
#
# LANES maps each runtime lane name to the catalog lane backing it
# (None = internal lane, not published in the catalog).
# tools/lane_checklist.py collects the keys and verifies every catalog
# lane has a runtime alias covered here (see ALIASES in that file).
#
# Update when a lane is added to either side; lane_checklist is the gate.

LANES = {
    "bank77": "banking77",
    "civic": "civic",
    "civic_fr": "civic_fr",
    "clinc": "clinc150",
    "clinc2": "clinc150",
    "eq": "eq_tone",
    "helpdesk2": "helpdesk",
    "it_helpdesk": "helpdesk",
    "mairie": None,      # internal lane, not yet published
    "mairie_c": None,
}
