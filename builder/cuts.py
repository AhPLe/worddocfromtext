"""Cut maps: fenced yaml blocks inside the cut-map section.

v1 grammar (kickoff): cut, exclude, include, title_overrides, summary.
Deliberately a MINI YAML subset (stdlib-only): `key: value`,
`key: [a, b]`, and one-level nested `key:` + indented `sub: value`
pairs. Trailing ` # comments` are stripped from unquoted values.

M1 applies only `exclude`. include / title_overrides / summary are
parsed and validated but their APPLICATION is deferred to M3 — the
representation of default-off bullets and summary/title variants is a
design-session decision to settle against the real master, not
hypothetically. Using them today produces a cut-feature-deferred WARN
at build time (see context.build_context).
"""

from .findings import Finding, ERROR, WARN
from .context import section_role

CUT_KEYS = {"cut", "title_overrides", "summary", "exclude", "include"}


def default_cut():
    return {"name": "default", "line": 0, "exclude": [], "include": [],
            "title_overrides": {}, "summary": ""}


def _clean_scalar(v):
    v = v.strip()
    if v and not v.startswith(('"', "'")) and " #" in v:
        v = v.split(" #", 1)[0].rstrip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def _parse_block(text, base_line, findings):
    """Parse one cut block's mini-YAML into a plain dict."""
    data, cur_map = {}, None
    for i, raw in enumerate(text.split("\n")):
        ln = base_line + i
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if raw.startswith((" ", "\t")) and cur_map is not None:
            k, sep, v = s.partition(":")
            if not sep:
                findings.append(Finding(ERROR, "cutmap-syntax", ln,
                                        f"expected 'key: value', got: {s!r}"))
                continue
            data[cur_map][k.strip()] = _clean_scalar(v)
            continue
        cur_map = None
        k, sep, v = s.partition(":")
        if not sep:
            findings.append(Finding(ERROR, "cutmap-syntax", ln,
                                    f"expected 'key: value', got: {s!r}"))
            continue
        k = k.strip()
        if k not in CUT_KEYS:
            findings.append(Finding(WARN, "cutmap-unknown-key", ln,
                                    f"unknown cut-map key '{k}' (v1 grammar: "
                                    f"{sorted(CUT_KEYS)})"))
        v = v.strip()
        if not v:
            data[k] = {}
            cur_map = k
        elif v.startswith("["):
            body = _clean_scalar(v).strip("[]")
            data[k] = [_clean_scalar(p) for p in body.split(",") if p.strip()]
        else:
            data[k] = _clean_scalar(v)
    return data


def find_cuts(doc):
    """Return ({name: cut_spec}, findings). 'default' always exists."""
    findings = []
    cuts = {"default": default_cut()}
    for sec in doc.sections:
        if (section_role(sec.heading) != "non_shipping"
                or "cut map" not in sec.heading.lower()):
            continue
        blocks = list(sec.blocks)
        for ent in sec.entries:
            blocks.extend(ent.blocks)
        for blk in blocks:
            if blk.kind != "code" or blk.lang not in ("", "yaml", "yml"):
                continue
            data = _parse_block(blk.text, blk.line, findings)
            name = str(data.get("cut", "")).strip()
            if not name:
                findings.append(Finding(ERROR, "cutmap-missing-name", blk.line,
                                        "cut block has no 'cut:' key"))
                continue
            if name == "default":
                # one block may CONFIGURE the built-in default cut —
                # its exclude list is the default-off set that named
                # cuts inherit (and can re-enable via include).
                if cuts["default"]["line"]:
                    findings.append(Finding(ERROR, "cutmap-duplicate",
                                            blk.line,
                                            "the default cut is configured "
                                            "twice"))
                    continue
                spec = cuts["default"]
            elif name in cuts:
                findings.append(Finding(ERROR, "cutmap-duplicate", blk.line,
                                        f"cut '{name}' defined twice"))
                continue
            else:
                spec = default_cut()
                cuts[name] = spec
            spec["name"] = name
            spec["line"] = blk.line
            for key in ("exclude", "include"):
                val = data.get(key, [])
                if isinstance(val, str):
                    val = [val] if val else []
                spec[key] = val
            tov = data.get("title_overrides", {})
            spec["title_overrides"] = tov if isinstance(tov, dict) else {}
            summ = data.get("summary", "")
            spec["summary"] = summ if isinstance(summ, str) else ""
            if name == "default" and spec["include"]:
                findings.append(Finding(WARN, "cutmap-default-include",
                                        blk.line,
                                        "'include' on the default cut has "
                                        "no effect (nothing to re-enable)"))
    return cuts, findings
