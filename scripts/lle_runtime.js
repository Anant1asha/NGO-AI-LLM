/* AASHA AIOS — Dual-Layer Language Learning Engine (LLE) Runtime */

const CONN = {
  and:"और", but:"लेकिन", because:"क्योंकि", so:"इसलिए", if:"अगर", when:"जब", while:"जबकि",
  although:"हालांकि", or:"या", therefore:"इसलिए", however:"परंतु", since:"चूंकि", unless:"जब तक नहीं"
};

function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function escA(s){ return String(s).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function normalizeWord(w){
  return String(w).toLowerCase().replace(/[’']s$/,"").replace(/[^a-z\-]/g,"");
}

function lookupWord(raw){
  const n = normalizeWord(raw);
  if (WM2[n]) return {known:true, h:WM2[n].h, p:WM2[n].p||""};
  const base = n.replace(/(ing|ed|es|s|ly)$/,"");
  if (WM2[base]) return {known:true, h:WM2[base].h, p:WM2[base].p||""};
  return {known:false, h:"(शब्दकोश में देखें)", p:""};
}

function rtText(text){
  const shielded = [];
  text = text.replace(/\{\{([\s\S]*?)\}\}/g, function(m,g){
    shielded.push(g);
    return "\u0001" + (shielded.length-1) + "\u0001";
  });
  const parts = text.split(/(<[^>]+>|\u0001\d+\u0001)/g);
  let connCount = 0;
  return parts.map(function(seg){
    if (/^<[^>]+>$/.test(seg)) return seg;
    const sm = seg.match(/^\u0001(\d+)\u0001$/);
    if (sm) return esc(shielded[+sm[1]]);
    return seg.replace(/([A-Za-z][A-Za-z'\-]*)|([.!?]+\s*)/g, function(m, word, punc){
      if (punc){ connCount = 0; return punc; }
      if (!word) return m;
      if (/^\d/.test(word)) return word;
      const low = word.toLowerCase();
      if (CONN[low] && connCount < 4){
        connCount++;
        return '<span class="conn" title="connector">' + word + ' (' + CONN[low] + ')</span>';
      }
      return '<span class="tapable" data-w="' + escA(normalizeWord(word)) + '" tabindex="0" role="button">' + word + '</span>';
    });
  }).join("");
}

function attachHi(el, hi){
  if(el && (el.textContent||'').replace(/\s+/g,' ').trim().length < 6) return;
  if (!hi) return;
  if (el.dataset.hiDone) return; el.dataset.hiDone = "1";
  const wrap = document.createElement("div"); wrap.className = "hiWrap";
  const btn = document.createElement("button"); btn.type="button"; btn.className="hiBtn";
  btn.setAttribute("aria-expanded","false"); btn.setAttribute("aria-label","Show Hindi translation");
  btn.textContent = "अ";
  const box = document.createElement("div"); box.className="hiBox"; box.hidden=true; box.setAttribute("lang","hi");
  box.textContent = hi;
  btn.addEventListener("click", function(e){
    e.stopPropagation();
    const open = box.hidden; box.hidden = !open; wrap.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", String(open));
    btn.classList.toggle("on", open);
  });
  wrap.appendChild(btn); wrap.appendChild(box); el.appendChild(wrap);
}

function applyLang(root){
  (root||document).querySelectorAll("[data-lang]").forEach(function(el){
    if (el.dataset.langDone) return;
    const en = (el.dataset.hi ? "" : el.textContent).replace(/\s+/g," ").trim();
    el.innerHTML = rtText(el.innerHTML);
    el.dataset.langDone = "1";
    attachHi(el, el.dataset.hi || PH[en]);
  });
  bindTaps(root||document);
}

function lang(root){
  if (!root) return;
  const els = root.querySelectorAll("[data-lang]");
  for (let i=0; i<els.length; i++){
    delete els[i].dataset.langDone;
    delete els[i].dataset.hiDone;
  }
  applyLang(root);
}

function bindTaps(root){
  (root||document).querySelectorAll(".tapable").forEach(function(el){
    if (el.dataset.bound) return; el.dataset.bound = "1";
    const open = function(){ showWord(el.dataset.w); };
    el.addEventListener("click", open);
    el.addEventListener("keydown", function(e){
      if (e.key==="Enter"||e.key===" "){ e.preventDefault(); open(); }
    });
  });
}

function showWord(w){
  const r = lookupWord(w);
  const eW=document.getElementById("wpWord"), eH=document.getElementById("wpHindi"), eP=document.getElementById("wpPron");
  if(eW) eW.textContent = w;
  if(eH) eH.textContent = r.h;
  if(eP) eP.textContent = (r.known && r.p) ? "उच्चारण · " + r.p : "";
  const panel = document.getElementById("wp");
  if(!panel) return;
  panel.classList.add("up"); panel.dataset.cur = w;
  speak(w);
}

function closeWord(){
  const p = document.getElementById("wp");
  if(p) p.classList.remove("up");
}

let lastUtter = null;
function speak(text){
  try{
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    lastUtter = new SpeechSynthesisUtterance(text);
    lastUtter.rate = 0.85; lastUtter.lang = "en-IN";
    window.speechSynthesis.speak(lastUtter);
  }catch(e){}
}

(function bindWordPanel(){
  const closeBtn = document.getElementById("wpClose");
  if(closeBtn) closeBtn.addEventListener("click", function(e){
    e.preventDefault(); e.stopPropagation(); closeWord();
  });
  const spk = document.getElementById("wpSpeak");
  if(spk) spk.addEventListener("click", function(e){
    e.preventDefault(); e.stopPropagation();
    const p = document.getElementById("wp");
    if(p && p.dataset.cur) speak(p.dataset.cur);
  });
  document.addEventListener("keydown", function(e){
    if(e.key === "Escape" || e.key === "Esc") closeWord();
  });
  document.addEventListener("click", function(e){
    const p = document.getElementById("wp");
    if(!p || !p.classList.contains("up")) return;
    if(p.contains(e.target)) return;
    if(e.target && e.target.classList && e.target.classList.contains("tapable")) return;
    closeWord();
  }, true);
})();
