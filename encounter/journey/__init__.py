"""Care journey: one patient, several connected interactions, one shared record with provenance.

A journey is data (encounter/journeys/*.json): an ordered list of stages, each mapped to an interaction type
from contracts/enums.yaml and playable by a learner in a different professional role. Every stage reads and
writes the same shared record; a stage nobody plays is resolved by a seeded sampler-equivalent. Patient-facing
stages run on the existing disclosure engine, so the grounding rules are the ones the single encounter uses.

    definition.py  journey definitions: load, validate, list
    record.py      the shared record: entries with provenance, discrepancies (authored only)
    stages.py      stage-scoped case view, ledger -> record sync, sampler-equivalent, stage objectives
    handoff.py     SBAR grading against the record and the receiving colleague (offline rules / model wording)
    synthesis.py   care plan and debrief, assembled only from the record
    manager.py     journey instances on disk, orchestration, interaction-contract results
    api.py         FastAPI router (included by encounter.api)
"""
