"""Targeted, text-level edit of ONE attribute block in a catalog YAML file.

Several agents edit the catalog files concurrently, so nothing here re-serialises a whole file: the file is
re-read immediately before each edit, only the lines of the addressed attribute are replaced (or a new
attribute is appended to its parent block), and everything else is left byte-for-byte as it was.
The shape of an existing value is never changed (list length, map keys, scalar-ness) - the simulator reads by key/index.
"""
from __future__ import annotations

import pathlib
import re

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_content(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("#")


def _block_end(lines: list[str], start: int) -> int:
    """Index one past the last line of the mapping entry that starts at `start`."""
    ind = _indent(lines[start])
    i = start + 1
    last = start
    while i < len(lines):
        if _is_content(lines[i]):
            li = _indent(lines[i])
            # a block sequence may sit at the same indent as its key ("key:\n- a\n- b")
            if li < ind or (li == ind and not lines[i].lstrip().startswith("- ")):
                break
            last = i
        i += 1
    return last + 1


def _find(lines: list[str], key: str, lo: int, hi: int, indent: int | None) -> int | None:
    pat = re.compile(r"^(\s*)" + re.escape(key) + r":(\s|$)")
    for i in range(lo, hi):
        m = pat.match(lines[i])
        if m and (indent is None or len(m.group(1)) == indent):
            return i
    return None


def _same_shape(old, new) -> bool:
    if old is None:
        return True
    if isinstance(old, list):
        return isinstance(new, list) and len(new) == len(old)
    if isinstance(old, dict):
        return isinstance(new, dict) and list(new.keys()) == list(old.keys())
    return not isinstance(new, (list, dict))


def set_attr(relpath: str, path: list[str], fields: dict, create: bool = False, drop: tuple = ()) -> str:
    """Merge `fields` into the attribute at `path` (e.g. ['shared','acuity_mix'] or
    ['variants','esi1','attributes','p_admit']). Returns 'updated' | 'created'."""
    f = REPO / relpath
    lines = f.read_text().split("\n")
    lo, hi, indent = 0, len(lines), 0
    for depth, key in enumerate(path):
        i = _find(lines, key, lo, hi, indent)
        last = depth == len(path) - 1
        if i is None:
            if not (last and create):
                raise KeyError(f"{relpath}: {'/'.join(path)} not found at '{key}'")
            attr = dict(fields)
            block = yaml.safe_dump({key: attr}, sort_keys=False, default_flow_style=False, width=140, allow_unicode=True)
            new = [(" " * indent + l) if l else l for l in block.rstrip("\n").split("\n")]
            lines[hi:hi] = new
            f.write_text("\n".join(lines))
            return "created"
        end = _block_end(lines, i)
        if last:
            old = yaml.safe_load("\n".join(lines[i:end]))[key]
            if "value" in fields and not _same_shape(old.get("value"), fields["value"]):
                raise ValueError(f"{relpath}: {'/'.join(path)} value shape would change: {old.get('value')!r} -> {fields['value']!r}")
            attr = dict(old)
            for k, v in fields.items():
                if k == "dist" and isinstance(old.get("dist"), dict):
                    attr["dist"] = {**old["dist"], **v}
                else:
                    attr[k] = v
            for k in drop:
                attr.pop(k, None)
            block = yaml.safe_dump({key: attr}, sort_keys=False, default_flow_style=False, width=140, allow_unicode=True)
            new = [(" " * indent + l) if l else l for l in block.rstrip("\n").split("\n")]
            lines[i:end] = new
            f.write_text("\n".join(lines))
            yaml.safe_load(f.read_text())  # still parses
            return "updated"
        # descend: children are the content lines inside (i, end)
        child = next((j for j in range(i + 1, end) if _is_content(lines[j])), None)
        indent = _indent(lines[child]) if child is not None else indent + 2
        lo, hi = i + 1, end
    raise AssertionError
