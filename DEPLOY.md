# Deploy guide — get the demos live

The three flagships ship two demo paths. The **static HTML demo** (`demo.html`) deploys free on GitHub Pages in five minutes. The **Streamlit prototype** (`src/app.py`) deploys free on Streamlit Community Cloud in ten minutes. Both are public; both link from the master README.

This guide assumes you've pushed the repo to GitHub. If you haven't, scroll to the bottom for the one-shot push commands.

---

## Path A — GitHub Pages (the fastest, for the static `demo.html` files)

GitHub Pages serves static HTML straight from the repo. Zero build, zero auth, zero cost.

**One-time setup:**

1. Go to `https://github.com/<your-username>/<your-repo>` → **Settings** → **Pages**
2. **Source:** Deploy from a branch
3. **Branch:** `main` · **Folder:** `/ (root)`
4. **Save**

**Wait 60–90 seconds.** Your demos go live at:

- `https://<your-username>.github.io/<your-repo>/01-model-drift-sentinel/demo.html`
- `https://<your-username>.github.io/<your-repo>/03-hallucination-containment/demo.html`

Update the master README's "Live demo" cells with these URLs. Done.

**Custom domain (optional):** If you own a domain, add a CNAME record pointing to `<your-username>.github.io` and configure under Pages → Custom domain.

---

## Path B — Streamlit Community Cloud (for the interactive `src/app.py` prototypes)

Streamlit Cloud is free for public repos and one of the fastest "from local to live URL" deploys in the industry. Five-minute setup.

**One-time setup:**

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app** → **From existing repo**
3. **Repository:** `<your-username>/<your-repo>`
4. **Branch:** `main`
5. **Main file path:** `01-model-drift-sentinel/src/app.py` (for DriftSentinel — repeat for HalluGuard and DealSentry)
6. **Advanced settings → Python version:** 3.11
7. **Deploy**

**Wait 2–3 minutes.** First deploy installs the `requirements.txt`. Subsequent reloads are seconds.

**Get the URL** in the form `https://<your-app-slug>.streamlit.app`. Update the master README.

**Pin a version.** In the app dashboard, lock to a specific git SHA so the live demo doesn't break on every commit. Re-deploy intentionally.

**Secrets** (if a project ever needs an Anthropic / OpenAI key): Streamlit Cloud has a **Secrets** UI in the app settings. Reference in code via `st.secrets["ANTHROPIC_API_KEY"]`. Don't commit keys.

---

## Path C — Hugging Face Spaces (alternative to Streamlit Cloud)

If you want the demos in front of an AI-savvy audience, Spaces is where they hang out. Same Python+Streamlit stack, slightly different deploy.

**One-time setup:**

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces) and click **Create new Space**
2. **Owner:** your username · **Space name:** e.g. `drift-sentinel`
3. **License:** MIT (matches the repo)
4. **SDK:** Streamlit
5. **Hardware:** CPU basic (free) — sufficient for these prototypes; the only GPU pieces are inference, which the prototypes mock
6. **Public** visibility
7. Push your code to the Space's git remote — Spaces is a git repo. The `app.py` and `requirements.txt` need to live at the root of the Space (not in `src/`), so add a top-level redirect file or restructure for Spaces.

**Wait 3–5 minutes.** Live URL: `https://huggingface.co/spaces/<your-username>/drift-sentinel`.

**Trade-offs vs Streamlit Cloud:**

- Spaces is more visible to the AI/ML community (the audience that will actually click through your portfolio).
- Streamlit Cloud is closer to a one-click deploy if your `app.py` lives inside `src/` like ours does.
- Recommendation: ship to Streamlit Cloud first (fastest), Spaces second (broader audience).

---

## Path D — Vercel (for a polished marketing landing page wrapping the demos)

If you want a single domain like `vijaysaharan.dev` that lists all three flagships with logos, then deep-links to each demo, Vercel is the move.

**One-time setup:**

1. Sign in to [vercel.com](https://vercel.com) with GitHub
2. **Import Project** → select your portfolio repo
3. **Framework Preset:** Other (since the repo is content + Streamlit, not a Next.js app)
4. **Build Command:** (leave empty)
5. **Output Directory:** `.` (the repo root, so GitHub Pages-equivalent serving)
6. **Deploy**

Custom domain in 2 clicks. Vercel gives you `<your-project>.vercel.app` immediately.

**The clever move:** Build a tiny `index.html` at the repo root that's the actual landing page (hero, three flagship cards, links to the demos). Vercel serves that as the homepage; the deep-link demos live at `/01-model-drift-sentinel/demo.html` etc. Now your LinkedIn link is a single domain.

---

## Pushing the repo to GitHub (if you haven't)

```bash
# From the portfolio root (after cp -R from ~/Library/...)
cd ~/Desktop/ai-pm-portfolio

# Clean up the orphan folder before first push
rm -rf 01-model-risk-console
rm -f .DS_Store

# Initialize git
git init
git add .
git commit -m "Initial portfolio drop: 3 flagships + 7 roadmap"

# Option 1 — using gh CLI (install: brew install gh)
gh repo create vijaysaharan/ai-pm-portfolio --public --source=. --push

# Option 2 — manual: create the repo on github.com first, then:
git remote add origin https://github.com/vijaysaharan/ai-pm-portfolio.git
git branch -M main
git push -u origin main
```

---

## Recommended deploy order (90 minutes end-to-end)

1. **Push to GitHub** (10 min)
2. **Enable GitHub Pages** for the static demos (5 min) → all three `demo.html` files live
3. **Deploy HalluGuard's Streamlit** to Streamlit Cloud (10 min) → it has the most polished UI, ship it first
4. **Update master README** with the four live URLs (5 min)
5. **Deploy DriftSentinel + DealSentry Streamlits** (15 min)
6. **Optional — Hugging Face Space** for HalluGuard (15 min) for AI/ML community visibility
7. **Optional — Vercel landing page** with custom domain (30 min) if you want `vijaysaharan.dev`

After step 5 you have **six live demo URLs**: three GitHub Pages static pages + three Streamlit Cloud apps. That's enough to ship the LinkedIn launch post.

---

## Path E — Record a 30-second Loom and embed it in the README

The single highest-ROI thing you can do after the demos are live. Recruiters spend 9 seconds on a GitHub repo. A pinned video at the top of the README converts that 9 seconds into 60. Loom is free for short clips, no editing required.

**Setup (one time, 3 minutes):**

1. Install [Loom](https://www.loom.com/desktop) (free tier covers everything we need).
2. Create an account. Free plan = unlimited videos under 5 minutes.

**Record DriftSentinel — 30 seconds, four shots:**

1. **Open `demo.html` in your browser** (or the live Streamlit Cloud URL once deployed).
2. **Hit Loom record → Screen + small webcam circle.** The webcam circle in the corner is what makes it feel like a person, not a screen-recording dump.
3. **Script (read once, then ad-lib):**
   - "DriftSentinel — production AI caught decaying 69 days earlier."
   - *click "Run all 8 models"*
   - "Eight models, 90 days of synthetic traffic, drift injected on day 60. Watch what each maturity level catches."
   - *the cards fill in: quarterly attestation says GREEN — wrong. Basic PSI catches three of four. DriftSentinel catches all eight, including the GenAI vendor silent update."*
   - "MRM evidence bundle assembled in 3.2 seconds. Validator attestation in a day instead of three weeks. Fork the repo to run it on your fleet."
4. **Stop. Loom auto-uploads. Copy the link.**

**Repeat for HalluGuard and DealSentry** (open their `demo.html` files, click through, narrate). 30 seconds each. Total: 90 seconds of recording, 5 minutes of total work.

**Embed in the README:**

```markdown
## ▶ 30-second demo

[![Watch the demo](https://cdn.loom.com/sessions/thumbnails/<video-id>-with-play.gif)](https://www.loom.com/share/<video-id>)
```

Loom gives you the thumbnail + play overlay GIF on every video page (right side panel → "Get embed code"). The result: a clickable thumbnail at the top of the README that plays the video on Loom in the same browser tab.

**Pro tips:**

- **First take. Don't edit.** Polished video is a tell that you spent more time on the video than the product. Imperfect is more credible.
- **No music, no intro card, no outro card.** Get to the demo in 3 seconds. Anything else is a recruiter dropoff trigger.
- **Webcam circle on.** Faces convert. Screenshare-only feels like a tutorial; webcam + screen feels like a person showing you their work.
- **Loom transcript is free.** Click "Caption" → enable. Adds an accessibility win and SEO that Loom's player surfaces.
- **Pinned tweet / LinkedIn post:** drop the Loom link directly. LinkedIn auto-embeds with a preview frame.

**If Loom isn't your speed:** QuickTime Screen Recording (Mac, built-in, Cmd+Shift+5) → upload to YouTube Unlisted. Same outcome, slightly more friction. Avoid.

---

## Common deploy gotchas

- **Streamlit Cloud import errors:** make sure `requirements.txt` exists in the same folder as `app.py`. Pinning versions (e.g. `streamlit>=1.32`) avoids breakage on Streamlit's nightly platform updates.
- **GitHub Pages 404 on demo.html:** the URL is case-sensitive. `Demo.html` ≠ `demo.html`. Folder names too.
- **Hugging Face Space "files in subfolder":** Spaces expect `app.py` at the Space root. Easiest fix: create a separate Space repo per flagship with the relevant project files copied to its root.
- **Custom domain SSL:** GitHub Pages and Vercel auto-issue Let's Encrypt certs. Wait 5–10 minutes after DNS propagation.
- **Free-tier sleep:** Streamlit Cloud apps idle to sleep after ~7 days of no traffic; first request after sleep takes 30–60 seconds. Hugging Face Spaces don't sleep but are slower at cold start.
