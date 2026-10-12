"""The `layout_edit` override of load_scenario: counterfactual capacity edits used by rl/attribution.py."""
import collections

import pytest
import torch

from sim import HospitalSim, load_scenario
from sim.config import apply_layout_edit

H = {"hospital_id": "rwjuh_nb"}


def counts(scn):
    lm = scn.layout
    c = collections.Counter(b["cls"] for b in lm.bays if b["exists0"])
    return dict(resus=c[0], main=c[1], fast=c[2], peds=c[3], hall=c[4], ward=lm.ward_cap, ct=lm.scan_units["ct"], xray=lm.scan_units["xray"],
                triage=lm.n_triage_rooms)


def test_default_is_unchanged():
    a, b = load_scenario("normal_week", dict(H)), load_scenario("normal_week", dict(H, layout_edit=None))
    assert counts(a) == counts(b) and a.layout.legs == b.layout.legs and a.layout_edit == [] and "layout_edit" not in a.overrides
    assert [r["capacity"] for r in a.layout.rooms] == [r["capacity"] for r in b.layout.rooms]


@pytest.mark.parametrize("edit,key,delta", [
    ({"remove": {"treatment_bay": 1}}, "main", -1), ({"add": {"treatment_bay": 4}}, "main", 4), ({"remove": {"resus_bay": 1}}, "resus", -1),
    ({"add": {"fast_track": 1}}, "fast", 1), ({"remove": {"peds_ed": 2}}, "peds", -2), ({"remove": {"ward_unit": 8}}, "ward", -8),
    ({"add": {"ward_unit": 1}}, "ward", 1), ({"remove": {"ct": 1}}, "ct", -1), ({"add": {"ct": 1}}, "ct", 1), ({"remove": {"xray": 1}}, "xray", -1),
    ({"add": {"triage": 1}}, "triage", 1), ({"remove": {"triage": 1}}, "triage", -1)])
def test_exactly_one_count_changes(edit, key, delta):
    base = counts(load_scenario("normal_week", dict(H)))
    scn = load_scenario("normal_week", dict(H, layout_edit=edit))
    got = counts(scn)
    assert got == dict(base, **{key: base[key] + delta})
    assert len(scn.layout_edit) == abs(delta) and scn.overrides["layout_edit"] == edit
    # the simulator's own tables follow the edited layout
    sim = HospitalSim(scn, batch_size=1, device="cpu", seed=1)
    assert int(sim.cfg["ward_cap0"]) == got["ward"] and sim.eq_units0 == [got["xray"], got["ct"]]
    assert int((sim.bay_exists0 & sim.bay_is[1]).sum()) == got["main"]
    assert int(sim.scn.layout.n_triage_rooms) == got["triage"]
    # zone walking distances barely move (units are taken from the middle of the class; scanners keep their rooms)
    legs0 = load_scenario("normal_week", dict(H)).layout.legs[0]
    assert max(abs(a - b) for a, b in zip(scn.layout.legs[0], legs0)) < 2.0
    sim.step()
    assert torch.isfinite(sim.observe()).all()


def test_hallway_spaces_are_never_edited_and_errors_are_loud():
    lay = dict(rooms=[dict(id="a", type="treatment_bay", x=0, z=0, capacity=1, catalog_ref="space/hallway_overflow"),
                      dict(id="b", type="treatment_bay", x=1, z=0, capacity=1, catalog_ref="space/treatment_bay")], equipment=[dict(id="c1", type="ct")])
    done = apply_layout_edit(lay, {"remove": {"treatment_bay": 1}}, {"treatment_bay": "main"})
    assert [d["id"] for d in done] == ["b"] and lay["rooms"][0]["capacity"] == 1 and lay["rooms"][1]["capacity"] == 0
    with pytest.raises(ValueError):
        apply_layout_edit(lay, {"remove": {"treatment_bay": 1}}, {"treatment_bay": "main"})
    with pytest.raises(ValueError):
        apply_layout_edit(lay, {"add": {"no_such_room": 1}})
    apply_layout_edit(lay, {"remove": {"ct": 1}})
    with pytest.raises(ValueError):
        apply_layout_edit(lay, {"remove": {"ct": 1}})
