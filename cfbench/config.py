"""Config loader. No fallback defaults: a missing key raises KeyError."""

import copy
import json
import os
import tomllib

from cfbench import paths


def load_toml(name: str) -> dict:
    with open(paths.CONFIG / name, "rb") as f:
        return tomllib.load(f)


def load_json(name: str):
    with open(paths.CONFIG / name, encoding="utf-8") as f:
        return json.load(f)


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(profile: str | None = None) -> dict:
    if profile is None:
        profile = os.environ.get("CFB_PROFILE") or "full"
    cfg = load_toml("bench.toml")
    profiles = cfg.pop("profiles", {})
    if profile == "full":
        return cfg
    if profile not in profiles:
        raise ValueError(f"unknown profile {profile!r}")
    return _merge(cfg, profiles[profile])
