"""Animated themes. Colours are CSS variables registered with @property, so switching theme
cross-fades every colour smoothly, and a marigold/aubergine wipe sweeps across the screen."""
from .config import THEMES

PROPS = ["bg1", "bg2", "bg3", "surface", "field", "text", "muted", "accent", "accent2", "onacc", "border"]

BASE = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Inter:wght@400;500;600&display=swap');
html,body,.stApp,button,input,textarea{font-family:Inter,system-ui,sans-serif}
.stApp{background:linear-gradient(150deg,var(--bg1),var(--bg2) 55%,var(--bg3));background-attachment:fixed;color:var(--text);animation:themeIn_ID .8s ease}
@keyframes themeIn_ID{from{opacity:.35}to{opacity:1}}
.wipe{position:fixed;inset:0;z-index:99999;pointer-events:none;opacity:0;background:linear-gradient(135deg,var(--accent),var(--accent2));animation:wipe_ID 1.1s ease-in-out}
@keyframes wipe_ID{0%{clip-path:circle(0% at 96% 4%);opacity:.9}70%{opacity:.5}100%{clip-path:circle(160% at 96% 4%);opacity:0}}
.stApp::before,.stApp::after{content:"";position:fixed;inset:-12%;z-index:0;pointer-events:none}
.stApp::before{background:radial-gradient(38vw 38vw at 12% 20%,color-mix(in srgb,var(--accent) 26%,transparent),transparent 62%),radial-gradient(34vw 34vw at 88% 82%,color-mix(in srgb,var(--accent2) 22%,transparent),transparent 62%);animation:drift1 30s ease-in-out infinite}
.stApp::after{background:radial-gradient(30vw 30vw at 80% 12%,color-mix(in srgb,var(--text) 8%,transparent),transparent 62%);animation:drift2 36s ease-in-out infinite}
@keyframes drift1{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(6vw,5vh) scale(1.14)}}
@keyframes drift2{0%,100%{transform:translate(0,0)}50%{transform:translate(-5vw,6vh) scale(1.1)}}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes blurIn{from{opacity:0;filter:blur(14px);transform:translateY(10px) scale(.98)}to{opacity:1;filter:blur(0);transform:none}}
@keyframes dots{0%,80%,100%{transform:scale(.55);opacity:.35}40%{transform:scale(1);opacity:1}}
[data-testid="stMain"]{position:relative;z-index:1}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stAppDeployButton"],#MainMenu,[data-testid="stMainMenu"]{display:none!important}
.block-container{max-width:980px!important;padding-top:2rem;padding-bottom:7rem}
[data-testid="stBottom"],[data-testid="stBottom"]>div,[data-testid="stBottomBlockContainer"]{background:transparent!important}
[data-testid="stBottomBlockContainer"]{max-width:980px!important}
/* text */
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp [data-testid="stMarkdownContainer"],.stApp [data-testid="stWidgetLabel"] *{color:var(--text)}
.stApp [data-testid="stCaptionContainer"] *{color:var(--muted)!important}
.stApp h1,.stApp h2,.stApp h3{font-family:Fraunces,Georgia,serif;letter-spacing:-.01em}
.eyebrow{font-size:.72rem;letter-spacing:.2em;text-transform:uppercase;font-weight:600;color:var(--muted);display:flex;align-items:center;gap:10px}
.eyebrow::after{content:"";height:1px;width:46px;background:var(--text);opacity:.5}
.display{font-family:Fraunces,Georgia,serif;font-weight:700;font-size:clamp(2.3rem,5.2vw,3.9rem);line-height:1.05;letter-spacing:-.02em;color:var(--text);margin:.5rem 0 .6rem}
.display .hl{background:var(--accent);color:var(--onacc);padding:0 .25em;border-radius:.18em;box-decoration-break:clone;-webkit-box-decoration-break:clone}
.lead{color:var(--muted);font-size:1.08rem;max-width:620px;margin-bottom:1.4rem;animation:rise .8s .45s both}
.rv{display:inline-block;animation:blurIn 1s cubic-bezier(.2,.7,.2,1) both}
.greeting{font-family:Fraunces,Georgia,serif;font-weight:700;font-size:clamp(2rem,4.4vw,3.2rem);text-align:center;color:var(--text);margin:0 0 1.4rem}
.brand{font-family:Fraunces,Georgia,serif;font-size:1.5rem;font-weight:700;color:var(--text);margin:.1rem 0 .8rem}
.recents{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;font-weight:600;color:var(--muted);margin:.9rem 0 .2rem}
/* sidebar */
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--bg2),var(--bg3));border-right:1px solid var(--border)}
[data-testid="stSidebarCollapseButton"] *,[data-testid="stExpandSidebarButton"] *{color:var(--text)!important;opacity:1!important}
/* buttons */
.stApp .stButton>button,.stApp .stDownloadButton>button,.stApp [data-testid="stFormSubmitButton"]>button{background:var(--surface);border:1px solid var(--border);border-radius:14px;font-weight:500;min-height:2.6rem;transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease,background .2s ease}
.stApp .stButton>button *,.stApp .stDownloadButton>button *,.stApp [data-testid="stFormSubmitButton"]>button *{color:var(--text)!important}
.stApp .stButton>button:hover,.stApp .stDownloadButton>button:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 10px 24px color-mix(in srgb,var(--accent) 32%,transparent)}
.stApp button[kind="primary"],.stApp [data-testid="stBaseButton-primary"],.stApp [data-testid="stBaseButton-primaryFormSubmit"]{background:var(--accent)!important;border:0!important;font-weight:600}
.stApp button[kind="primary"] *,.stApp [data-testid="stBaseButton-primary"] *,.stApp [data-testid="stBaseButton-primaryFormSubmit"] *{color:var(--onacc)!important}
.stApp button[kind="primary"]:hover{filter:brightness(1.08)}
/* inputs */
.stApp [data-baseweb="input"],.stApp [data-baseweb="textarea"],.stApp [data-baseweb="select"]>div{background:var(--field)!important;border:1px solid var(--border)!important;border-radius:12px!important}
.stApp [data-baseweb="base-input"]{background:transparent!important;border:0!important}
.stApp input,.stApp textarea{color:var(--text)!important;-webkit-text-fill-color:var(--text)!important;caret-color:var(--accent)!important}
.stApp input::placeholder,.stApp textarea::placeholder{color:var(--muted)!important;-webkit-text-fill-color:var(--muted)!important;opacity:.9}
.stApp [data-baseweb="select"] *{color:var(--text)!important}
[data-baseweb="popover"] ul,[data-baseweb="popover"]>div{background:var(--bg2)!important;border-radius:12px}
[data-baseweb="popover"] li,[data-baseweb="popover"] li *{color:var(--text)!important}
[data-testid="stForm"]{background:var(--surface);border:1px solid var(--border);border-radius:22px;padding:1.5rem;backdrop-filter:blur(12px);animation:rise .8s .5s both}
[data-testid="stExpander"]{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:14px!important}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{color:var(--text)!important;background:transparent!important}
[data-testid="stFileUploaderDropzone"]{background:var(--surface)!important;border:2px dashed var(--accent)!important;border-radius:20px!important}
[data-testid="stFileUploaderDropzone"] *{color:var(--text)!important}
[data-testid="stSlider"] [role="slider"]{background:var(--accent)!important;box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 30%,transparent)!important}
[data-testid="stStatus"],[data-testid="stStatusWidget"]{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:14px!important}
.stApp code{background:color-mix(in srgb,var(--text) 10%,transparent)!important;color:var(--text)!important;border-radius:6px}
.stApp pre{background:color-mix(in srgb,var(--text) 8%,transparent)!important}
.stApp pre *{color:var(--text)!important}
/* navigation pills */
.st-key-page div[role="radiogroup"]{gap:.5rem;flex-wrap:wrap}
.st-key-page div[role="radiogroup"]>label{background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:.4rem 1.1rem;cursor:pointer;transition:transform .2s ease,background .3s ease}
.st-key-page div[role="radiogroup"]>label:hover{transform:translateY(-2px)}
.st-key-page div[role="radiogroup"]>label>div:first-child{display:none}
.st-key-page div[role="radiogroup"]>label:has(input:checked){background:var(--accent);border-color:var(--accent);box-shadow:0 8px 22px color-mix(in srgb,var(--accent) 40%,transparent)}
.st-key-page div[role="radiogroup"]>label:has(input:checked) *{color:var(--onacc)!important;font-weight:600}
/* chat */
[data-testid="stChatMessageAvatarUser"],[data-testid="stChatMessageAvatarAssistant"]{display:none!important}
[data-testid="stChatMessage"]{background:transparent;padding:.4rem 0;line-height:1.7;animation:rise .45s both}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] *{color:var(--text)}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){width:fit-content;max-width:86%;margin-left:auto;background:var(--surface);border:1px solid var(--border);border-radius:20px 20px 6px 20px;padding:.8rem 1.1rem}
[data-testid="stChatMessage"]:not(:has([data-testid="stChatMessageAvatarUser"])){border-left:3px solid var(--accent);padding-left:1rem;margin:.6rem 0}
[data-testid="stChatInput"]>div{background:var(--field)!important;border:1.5px solid var(--border)!important;border-radius:28px!important;box-shadow:0 12px 34px -12px color-mix(in srgb,var(--text) 35%,transparent);transition:border-color .25s,box-shadow .25s}
[data-testid="stChatInput"]>div:focus-within{border-color:var(--accent)!important;box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 24%,transparent)}
[data-testid="stChatInput"] textarea{color:var(--text)!important;-webkit-text-fill-color:var(--text)!important}
[data-testid="stChatInput"] button{background:var(--accent)!important;color:var(--onacc)!important;border-radius:50%!important}
[data-testid="stChatInput"] button svg{fill:var(--onacc)!important}
.st-key-hero_input [data-testid="stChatInput"]>div{min-height:90px;border-radius:32px!important}
.thinking{display:flex;gap:7px;padding:.7rem 0}.thinking span{width:9px;height:9px;border-radius:50%;background:var(--accent);animation:dots 1.2s infinite ease-in-out}
.thinking span:nth-child(2){animation-delay:.15s}.thinking span:nth-child(3){animation-delay:.3s}
/* chips, stats, tables */
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:.5rem 0}
.chip{border:1px solid var(--border);background:var(--surface);border-radius:999px;padding:.12rem .8rem;font-size:.8rem;color:var(--text)}
.chip b{color:var(--text);background:var(--accent);color:var(--onacc);border-radius:999px;padding:0 .45em;margin-right:.4em;font-size:.72rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:.8rem 0}
.stat{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:.8rem 1rem;animation:rise .6s both;transition:transform .25s}
.stat:hover{transform:translateY(-4px)}.stat small{display:block;color:var(--muted);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;font-weight:600}
.stat b{font-family:Fraunces,Georgia,serif;font-size:1.45rem;color:var(--text)}
.doc{display:flex;gap:12px;align-items:center;background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:.7rem 1rem;margin:.4rem 0}
.doc .ico{font-size:1.5rem}.doc b{color:var(--text)}.doc span{color:var(--muted);font-size:.85rem}
.tblwrap{overflow:auto;max-height:420px;border:1px solid var(--border);border-radius:14px;background:var(--surface)}
.tbl{border-collapse:collapse;width:100%;font-size:.85rem}
.tbl th{position:sticky;top:0;background:var(--bg2);color:var(--text);text-align:left;padding:.5rem .8rem;white-space:nowrap}
.tbl td{padding:.4rem .8rem;border-top:1px solid var(--border);color:var(--text);white-space:nowrap}
/* sidebar chat rows + action cards */
[data-testid="stSidebar"] .stButton>button{justify-content:flex-start;text-align:left}
[data-testid="stSidebar"] .stButton>button p{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
[class*="st-key-active_"] button{background:color-mix(in srgb,var(--accent) 24%,transparent)!important;border-color:var(--accent)!important}
[class*="st-key-del_"] button{justify-content:center!important;min-height:2.2rem;opacity:.65}
.st-key-new_chat button{justify-content:center!important}
[class*="st-key-chip_"] button,[class*="st-key-act_"] button{min-height:3.4rem;justify-content:flex-start;text-align:left;border-radius:18px}
[class*="st-key-chip_"],[class*="st-key-act_"]{animation:rise .7s both}
::selection{background:var(--accent);color:var(--onacc)}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
"""


def css(name: str) -> str:
    t = THEMES.get(name) or next(iter(THEMES.values()))
    reg = "".join(f"@property --{p}{{syntax:'<color>';inherits:true;initial-value:#000}}" for p in PROPS)
    root = (":root{" + "".join(f"--{p}:{t[p]};" for p in PROPS) + f"color-scheme:{t['scheme']};"
            + "transition:" + ",".join(f"--{p} .8s ease" for p in PROPS) + "}")
    uid = name.lower().replace(" ", "")
    return f"<style>{reg}{root}{BASE.replace('_ID', '_' + uid)}</style><div class=\"wipe\"></div>"


def plot_layout(name: str) -> dict:
    t = THEMES.get(name) or next(iter(THEMES.values()))
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=t["text"], family="Inter"),
                margin=dict(l=10, r=10, t=40, b=10), colorway=[t["accent"], t["accent2"], "#8E4585", "#B8860B", "#6C7A89"])
