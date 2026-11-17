# Notes Search

Paste in a math problem and it finds the pages in your own class notes that show how to solve it. It's a Mac app, it works for any class, and it all runs on your computer.

I built it to learn how retrieval (RAG) works, using my own vector calculus notes from last spring. It started as a tutor that answered questions with Claude. I liked the search part better, so that's what the app is now.

Most of the work was testing. I made a 100-question test set comparing embedding search, keyword search (BM25) and a mix of both. On the draft set, embedding search got the right section first 82% of the time and keyword search got 57%.

Built with [Claude Code](https://claude.com/claude-code). Claude wrote most of the code; I picked the plan and decide what the results mean.

## Where it's at
- Working: the search pipeline, the Mac app, the search experiments and unit tests. The test set is still a draft.
- Not done yet: the answer experiment (needs an API key) and a Windows version.
- My notes aren't included, since they're from a university course. Point it at your own PDF notes to try it.

## Notes Search (the desktop app)

**Using it:**
1. There's no download yet, so build the app (see **Building it** below) or run `python desktop.py` from source. Then drag **Notes Search.app** into Applications. It runs on Apple Silicon Macs (M1 or later) with macOS 12 or newer.
2. Open it. The first time, macOS blocks it, because the app isn't signed with a paid Apple developer ID. Open **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** (on older macOS, right-click the app and choose **Open**). After that it opens normally.
3. Click **Add notes**, name the subject, pick its symbol keyboard, and either upload PDFs or point at a folder of them. Indexing about 100 pages takes under a minute.
4. Pick the subject, then paste a problem or type a topic. The matching sections of your notes appear as images of the actual pages, best match first.

**Privacy:** notes, indexes and settings stay in `~/Library/Application Support/Notes Search`. Nothing is uploaded, and the search model ships inside the app, so searching works offline. Method-first search (optional) is the only feature that contacts the internet, and only if you set your own `ANTHROPIC_API_KEY`.

**What works best:** typed or LaTeX PDFs. Scanned or handwritten pages have no text to search, so the app skips them and says so.

**Building it** (macOS):
```bash
pip install -r requirements-app.txt
python -c "from vctutor.search import embedder; embedder()"        # puts the search model in data/models
B=~/Library/Caches/notes-search-build
pyinstaller notes_search.spec --noconfirm --distpath "$B/dist" --workpath "$B/work"
xattr -cr "$B/dist/Notes Search.app" && codesign -s - --force --deep "$B/dist/Notes Search.app"
```
Build outside iCloud Drive, because iCloud adds file attributes that macOS code signing rejects. The app is about 440 MB, including the search model (a 200 MB zip). To share it, zip it with `ditto -c -k --keepParent "Notes Search.app" "Notes Search-mac.zip"`, which keeps the app's signature intact. The build only runs on the kind of Mac it was built on (Apple Silicon here); Intel Macs and Windows need their own build. `python desktop.py` runs the same app from source.

## How it works

```
PDF notes ──► ingest ──► chunks ──► search ──► top 5 passages ──► Claude (+ SymPy tool) ──► answer with citations
```

1. **Ingest** (`vctutor/ingest.py`) reads each PDF with PyMuPDF.
   - LaTeX's big-operator font has no Unicode mapping, so PDF readers turn ∫, ∮ and ∑ into the letters Z, I and X. The ingester maps them back using the font name.
   - It writes exponents and subscripts as `x^2` and `x_0`, based on the size and height of the text.
   - Each file name gives the section number and title when it has one: `13.2.2 - Line Integrals (Lecture 34).pdf` becomes doc `13.2.2`, section `13.2`, and `Topic 1.3 - Integrating Factor - 2026-10-22.pdf` becomes `1.3`. Other names are used as titles.
   - Repeated page headers, footers and page numbers are dropped.
   - Notes are grouped into **collections**, one per subject, each with its own index under `data/collections/<subject>/`.
2. **Two chunkings:**
   - `fixed`: windows of 220 words with 40 words of overlap (491 chunks)
   - `section`: split at the bold headings in the notes, so each chunk is one definition or example (849 chunks)
3. **Three search methods** (`vctutor/search.py`):
   - `embedding`: [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5), a free local model run through ONNX Runtime (fastembed), with cosine similarity in NumPy. It gives the same vectors as the PyTorch version (cosine 1.0000 on the notes) about 40% faster, and keeps PyTorch out of the app.
   - `bm25`: keyword search
   - `hybrid`: reciprocal rank fusion of the two
4. **Whole sections ("units")**: the ingester also cuts each note at its section and "Example" headings, which are set larger than body text. Each unit keeps a whole worked example together, Step 1 through the conclusion (417 units, median 174 words).
   - Search runs on the small chunks.
   - Each hit is then widened to its unit (small-to-big retrieval), so the answer and the demo see the full example instead of steps 2–3 alone. Several hits in one unit merge.
5. **Method-first search** (`vctutor/rewrite.py`, optional, needs an API key). Questions usually name the topic but not the method: a line-integral problem says "line integral" but not "parametrize the curve". So search returns general notes on the topic.
   - With method-first on, a cheap Claude call (structured JSON output) names the solution method and writes a search query in the notes' words.
   - Both queries are searched, and the results are merged with reciprocal rank fusion. Rewrites are cached.
   - Pasted math is also normalized before any search: t⁴ → t^4, ⟨a, b⟩ → <a, b>, ∫ → "integral".
6. **Answer** (`vctutor/answer.py`) sends the top passages to Claude (Claude Haiku 5.5 by default). By default these are the widened units; `--context chunk` sends only the matched chunks.
   - Claude takes definitions and methods from the passages, cites passage IDs, and says what's missing when the notes don't cover something.
   - `--method none` asks Claude with no notes (closed book).
7. **SymPy tool** (`vctutor/tools.py`, `vctutor/mathtools.py`): Claude can send one SymPy expression at a time, for example `curl(vec(x*y, y*z, z*x))` or `integrate(x*y**2, (x, 0, 2), (y, 0, 3))`, and gets the exact result back.
   - The input is checked against a small character set, and dunder access is blocked, so it can't reach Python internals.
   - Each call has a 20-second limit.

## Test set (`eval/`)
100 questions, written for this project. `eval/REVIEW.md` is a readable sheet for checking them.

- **50 concept questions**, like "What does the Divergence Theorem relate?" Each is labeled with the section(s) that answer it, and scored by whether search returns a chunk from one of them. Three are phrased without the key term ("a tiny paddle wheel in a flowing fluid"), to test meaning-based search.
- **50 computation problems** (dot and cross products, planes, partial derivatives, gradients, tangent planes, double and triple integrals, line integrals, Green's, Stokes' and the Divergence Theorem). Each also has a hand label: its solution method, and which parts of the notes show that method (175 references in all).
  - Each has a SymPy `solution`, and `python -m vctutor.build_eval` computes the answer key from it.
  - Claude ends its answer with a `FINAL:` line, which `mathtools.grade` parses and compares symbolically. Planes may differ by a constant factor, and potential functions by an added constant.

## Results: search (100-question draft set)

Two levels of "right":
- **Topic:** a chunk from the expected section of the course (13.3 = line integrals), for all 100 questions.
- **Method:** for the 50 computation problems, a chunk from a part of the notes that shows *how to solve that problem*: hand labels naming those parts, such as "Part 2: The Parametric Method".

recall@k is the share of questions with a hit in the top k. MRR@10 is the average of 1/rank of the first hit.

**Topic level** (100 questions, with section headings in the index):

| Chunks | Search | recall@1 | recall@5 | MRR@10 |
|---|---|---|---|---|
| fixed | embedding | 82% | 96% | 0.89 |
| fixed | BM25 | 57% | 92% | 0.73 |
| fixed | hybrid | 79% | 97% | 0.86 |
| section | embedding | 74% | 97% | 0.83 |
| section | BM25 | 64% | 92% | 0.76 |
| section | hybrid | 71% | 96% | 0.82 |

**Method level** (50 computation problems). The columns compare chunks indexed by their text alone (an earlier build of the index) vs. with their section heading added (the current index):

| Chunks | Search | recall@1 (text only → + heading) | recall@5 | MRR@10 |
|---|---|---|---|---|
| fixed | embedding | 40% → **56%** | 80% → 84% | 0.56 → **0.68** |
| fixed | BM25 | 38% → 40% | 72% → 72% | 0.52 → 0.54 |
| fixed | hybrid | 44% → 56% | 74% → 78% | 0.57 → 0.66 |
| section | embedding | 50% → 52% | 84% → 84% | 0.65 → 0.66 |
| section | BM25 | 48% → 48% | 80% → 80% | 0.61 → 0.63 |
| section | hybrid | 56% → 56% | 84% → 86% | 0.67 → **0.69** |

What this shows:
- **Finding the method is much harder than finding the topic.** The best setup puts the right topic first 82% of the time but the right method first only 56% of the time. Scoring only at the topic level would have hidden this: it counted a passage on conservative-field equivalences as correct for a problem that needs the parametric method.
- **Adding each chunk's section heading to the indexed text** ("contextual chunk headers") raised method-level recall@1 on fixed chunks from 40% to 56% with embeddings. Section chunks barely changed, because they already start with their heading.
- **Meaning-based search beats keyword search** at both levels.
- **The top setups are within one or two problems of each other** (method MRR 0.66–0.69). The app uses fixed chunks with hybrid search.
- **Most remaining method misses are problems that don't name their method.** Examples: two integrals over disks that need polar coordinates, a region between two curves, f_xy, and a parametric line integral. Method-first search targets exactly these.

**A second subject, as a check that the app works beyond vector calculus.** On 10 hand-written problems over my differential equations notes (19 topic guides), fixed chunks with hybrid search put a page showing the right method first for 6 and in the top 3 for 7, the best of the six setups. Ten questions is only a sanity check, not a measurement.

Labels for the method level are in `eval/private/` (not published, because they quote the notes' headings). `python -m vctutor.labels` checks that every label still matches a section of the notes. The test set is a first draft, so treat these numbers as preliminary.

## Results: answers
Not run yet. `python -m vctutor.evaluate answers` runs 7 setups on the 50 computation problems, each adding one change, and grades every answer with SymPy:
1. closed book
2. basic RAG (embedding search, fixed chunks)
3. section chunks
4. hybrid search
5. whole sections as context
6. method-first search
7. that, plus the SymPy tool

`python -m vctutor.evaluate retrieval --method-first` measures what method-first search does to search alone.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp local_config.example.json local_config.json   # then set notes_dir to your folder of PDFs
python -m vctutor.ingest          # PDFs -> data/fixed and data/section chunks
python -m vctutor.search build    # embed the chunks (downloads the ~130 MB model once)
python -m vctutor.search "What does the curl measure?"   # compare the search methods

python -m vctutor.build_eval            # answer key + eval/REVIEW.md
python -m vctutor.evaluate retrieval    # search experiment (no API key needed)
python -m unittest discover tests       # unit tests (no notes or API key needed)

export ANTHROPIC_API_KEY=...            # from console.anthropic.com
python -m vctutor.answer --method hybrid --chunking section --tools "Find the curl of F = <xy, yz, zx>."
python -m vctutor.evaluate answers --limit 5   # cheap trial, then without --limit
```

Without `ANTHROPIC_API_KEY`, `answer` and `smoke_test` still run search and skip the Claude call. Set `VCT_CLAUDE_MODEL` to use a different model.

**Demo app (a page finder):** `streamlit run app.py`, then open http://localhost:8501.
- Paste a problem or type a topic, and it shows the sections of the notes that show how to solve it, best match first.
- **Symbol keyboard** under the search box (`vctutor/mathbox.py`, a Streamlit `components.v2` component): ∫ ∬ ∭ ∮ ∂ ∇ ∇× ∇·, ⟨ ⟩ · × |v| î ĵ k̂, ², ³, ^, √( ), e^( ), and π θ φ ρ ∞ ≤ ≥. Clicking a key inserts it at the cursor (⟨ ⟩, √( ) and |v| put the cursor inside). Enter searches. The search rewrites these symbols the way the notes' text spells them (⟨a, b⟩ → <a, b>, t⁴ → t^4, ∂ → "partial").
- Each section appears as an image cropped from the original PDF (`vctutor/render.py`), labeled like "Lecture 36 · Computing Line Integrals — The Parametric Method (p. 5)".
- It doesn't write answers. Claude's answers are in the command-line tool and the experiments.
- Search settings (method, chunking, number of matches, method-first search, debug views) are in a closed "Advanced settings" menu under the examples.
- Note images are rendered at 288 dpi so they stay sharp on high-resolution screens.
- **Design:** a warm off-white page, a plain serif headline ("Search the course notes", in Fraunces) over a sans-serif body (Inter) at an 18px base size, white rounded cards with soft shadows, and one indigo accent color. It adapts to phone screens.
- `.streamlit/config.toml` sets the theme and fonts (loaded from Google Fonts by the browser), hides the developer toolbar, serves the app only on this computer, and turns off usage stats.

## Data and privacy
The notes are my own study notes from a university vector calculus course, so they aren't in this repository. Everything built from them (`data/`, `results/`) and `local_config.json` is in `.gitignore`. To use the code, point `local_config.json` at any folder of PDF notes whose file names start with a section number.

## Known limitations
- In the extracted text that search and Claude read, display equations (fractions, matrices, limits under integrals) are partly scrambled. Prose and inline math are mostly clean. The demo shows page images instead.
- One person labeled the test set, and the expected sections are judgment calls: a topic can be covered in more than one place.
- Concept answers aren't graded automatically. Only search is scored for them.
