from pathlib import Path

from cfbench import paths, tools


def fake_runner(version_output="cargo-bloat 0.12.1", install_rc=0, log=None):
    log = log if log is not None else []

    def run(argv):
        log.append(argv)
        if argv[0] == "cargo":
            if install_rc == 0:
                bin_dir = paths.THIRD_PARTY / "tools" / "bin"
                bin_dir.mkdir(parents=True, exist_ok=True)
                (bin_dir / "cargo-bloat").write_text("x")
            return install_rc, "error: could not compile\nline2\nfinal failure line"
        return 0, version_output

    return run, log


def test_installed_tool_is_not_reinstalled(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "THIRD_PARTY", tmp_path)
    (tmp_path / "tools" / "bin").mkdir(parents=True)
    (tmp_path / "tools" / "bin" / "cargo-bloat").write_text("x")
    run, log = fake_runner()
    st = tools.ensure("cargo-bloat", runner=run)
    assert st.ok and st.version == "0.12.1" and st.error is None
    assert all(a[0] != "cargo" for a in log)  # no install attempted


def test_install_failure_is_reported_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "THIRD_PARTY", tmp_path)
    run, _ = fake_runner(install_rc=101)
    st = tools.ensure("cargo-bloat", runner=run)
    assert st.ok is False
    assert "install failed (101)" in st.error and "final failure line" in st.error

    def boom(argv):
        raise RuntimeError("no cargo")

    st = tools.ensure("cargo-audit", runner=boom)
    assert st.ok is False and "RuntimeError" in st.error


def test_install_command_uses_locked_version_and_local_root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "THIRD_PARTY", tmp_path)
    run, log = fake_runner()
    st = tools.ensure("cargo-bloat", runner=run)
    assert st.ok
    cmd = log[0]
    assert cmd[:3] == ["cargo", "+stable", "install"]
    assert "--locked" in cmd
    assert cmd[cmd.index("--root") + 1] == str(Path(tmp_path) / "tools")
    assert cmd[cmd.index("--version") + 1] == "0.12.1" and "cargo-bloat" in cmd


def test_wrong_installed_version_triggers_reinstall(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "THIRD_PARTY", tmp_path)
    (tmp_path / "tools" / "bin").mkdir(parents=True)
    (tmp_path / "tools" / "bin" / "cargo-bloat").write_text("x")
    versions = iter(["cargo-bloat 0.11.0", "cargo-bloat 0.12.1"])
    log = []

    def run(argv):
        log.append(argv[0])
        return (0, "") if argv[0] == "cargo" else (0, next(versions))

    assert tools.ensure("cargo-bloat", runner=run).ok
    assert log.count("cargo") == 1


def test_version_check_uses_configured_args(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "THIRD_PARTY", tmp_path)
    (tmp_path / "tools" / "bin").mkdir(parents=True)
    (tmp_path / "tools" / "bin" / "cargo-bloat").write_text("x")
    seen = []

    def run(argv):
        seen.append(argv[1:])
        return 0, "0.12.1"

    assert tools.ensure("cargo-bloat", runner=run).ok
    assert seen == [["bloat", "--version"]]  # cargo-bloat only runs as a cargo subcommand


def test_pins_cover_every_tool():
    # later phases add tokei and rust-code-analysis-cli; the first three stay pinned
    assert {"cargo-audit", "cargo-bloat", "cargo-geiger", "tokei"} <= set(tools.all_names())
