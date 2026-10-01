import os

HERMETIC_GIT_ARGS = [
    "-c", "user.email=t@t",
    "-c", "user.name=t",
    "-c", "commit.gpgsign=false",
    "-c", "tag.gpgsign=false",
    "-c", "gpg.format=openpgp",
]  # fmt: skip


def hermetic_git_env():
    """Environment that ignores the user's global and system git config."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env
