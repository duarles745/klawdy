"""Test setup: point HOME/XDG dirs to a throw-away folder BEFORE importing klawdy."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")
TMP = tempfile.mkdtemp(prefix="klawdy-tests-")
for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "home/.config"), ("XDG_CACHE_HOME", "home/.cache"),
                 ("XDG_RUNTIME_DIR", "run")):
    os.environ[var] = os.path.join(TMP, sub)
    os.makedirs(os.environ[var], exist_ok=True)
os.environ["LANG"] = "pt_BR.UTF-8"
os.environ.pop("LANGUAGE", None)
os.environ.pop("LC_ALL", None)
os.environ.pop("LC_MESSAGES", None)
sys.path.insert(0, APP)
