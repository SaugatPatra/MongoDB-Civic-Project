"""Dark 'urban operations' styling."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@500&display=swap');
html, body, [class*="css"], .stMarkdown { font-family: 'Space Grotesk', sans-serif; }
.stApp { background: radial-gradient(1200px 500px at 85% -10%, rgba(34,211,238,.10), transparent), #0B0F17; }
.block-container { padding-top: 1.4rem; max-width: 1400px; }
h1, h2, h3 { letter-spacing: -.02em; }
.hero { display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap; margin-bottom:.6rem; }
.hero h1 { margin:0; font-size:2rem; } .hero h1 span { color:#22D3EE; }
.hero p { margin:0; color:#8B97AB; font-size:.95rem; }
[data-testid="stMetric"] { background:#121826; border:1px solid #1F2A3D; border-radius:14px; padding:14px 16px; border-top:2px solid #22D3EE; }
[data-testid="stMetricValue"] { font-family:'JetBrains Mono', monospace; }
[data-testid="stMetricLabel"] p { color:#8B97AB; text-transform:uppercase; font-size:.72rem; letter-spacing:.08em; }
.pill { display:inline-block; padding:1px 10px; border-radius:999px; font-size:.72rem; font-weight:700; border:1px solid; }
.pill.red{color:#FB7185;border-color:#FB7185;background:rgba(244,63,94,.12)} .pill.orange{color:#FB923C;border-color:#FB923C;background:rgba(251,146,60,.12)}
.pill.yellow{color:#FACC15;border-color:#FACC15;background:rgba(250,204,21,.10)} .pill.cyan{color:#22D3EE;border-color:#22D3EE;background:rgba(34,211,238,.10)}
.pill.green{color:#4ADE80;border-color:#4ADE80;background:rgba(74,222,128,.10)} .pill.grey{color:#8B97AB;border-color:#3A465C}
.dispatch { display:flex; align-items:center; gap:12px; background:#121826; border:1px solid #1F2A3D; border-left:3px solid #22D3EE;
            border-radius:12px; padding:10px 12px; margin-bottom:8px; }
.dispatch .rank { font-family:'JetBrains Mono'; color:#5B6B85; font-size:1.1rem; }
.dispatch .body { flex:1; line-height:1.35; } .dispatch small { color:#8B97AB; }
.dispatch .score { font-family:'JetBrains Mono'; font-size:1.4rem; color:#FACC15; }
.notice { background:rgba(250,204,21,.08); border:1px solid rgba(250,204,21,.35); color:#FDE68A; border-radius:10px; padding:8px 12px; font-size:.85rem; }
@media (max-width: 640px) { .hero h1 { font-size:1.5rem; } .block-container { padding:1rem .8rem; } }
</style>
"""

def inject(): st.markdown(CSS, unsafe_allow_html=True)
