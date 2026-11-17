# PyInstaller recipe for the Notes Search desktop app.
#   B=~/Library/Caches/notes-search-build
#   pyinstaller notes_search.spec --noconfirm --distpath "$B/dist" --workpath "$B/work"
#   xattr -cr "$B/dist/Notes Search.app" && codesign -s - --force --deep "$B/dist/Notes Search.app"
# Build outside iCloud Drive: iCloud adds file attributes that macOS code signing rejects.
# The search model must be in
# data/models first: build any collection once, or run  python -c "from vctutor.search import embedder; embedder()"
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH)
MODELS = ROOT / "data" / "models"
assert any(MODELS.rglob("*.onnx")), "the search model isn't in data/models yet"

datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / ".streamlit" / "config.toml"), ".streamlit"),
    (str(MODELS), "models"),
]
datas += collect_data_files("streamlit")
datas += collect_data_files("fastembed")
for pkg in ("streamlit", "fastembed", "huggingface_hub", "tokenizers", "onnxruntime", "anthropic", "pymupdf"):
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

hiddenimports = ["vctutor", "vctutor.config", "vctutor.ingest", "vctutor.search", "vctutor.render",
                 "vctutor.mathbox", "vctutor.rewrite", "rank_bm25", "fastembed", "anthropic"]
hiddenimports += collect_submodules("streamlit")

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["torch", "torchvision", "transformers", "sentence_transformers", "sympy", "scipy", "sklearn",
              "matplotlib", "IPython", "jupyter", "notebook", "pytest", "tkinter", "vctutor.answer",
              "vctutor.tools", "vctutor.mathtools", "vctutor.evaluate", "vctutor.build_eval", "vctutor.smoke_test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Notes Search", console=False,
          argv_emulation=False, target_arch=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Notes Search")
app = BUNDLE(
    coll,
    name="Notes Search.app",
    icon=str(ROOT / "assets" / "NotesSearch.icns") if (ROOT / "assets" / "NotesSearch.icns").exists() else None,
    bundle_identifier="io.github.samsoncukor06.notes-search",
    info_plist={"CFBundleShortVersionString": "0.1.0", "NSHighResolutionCapable": True,
                "LSMinimumSystemVersion": "12.0"},
)
