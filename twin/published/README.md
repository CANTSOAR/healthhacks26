# twin/published/<ccn>.yaml - facts a hospital publishes about itself

Optional, hand-entered. Public datasets do not carry an ED's number of treatment rooms; some hospitals state it on their own
pages. A fact entered here must have the exact quote, the URL and the date it was read; it is tagged `literature` and replaces
the corresponding rule in `twin/derive.py` (`ed_treatment_spaces`, `resus_bays`) or is added as an extra attribute.
Nothing here is fetched automatically, and a hospital without a file simply gets the stated rules.
