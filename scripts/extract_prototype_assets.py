import re
import json
from pathlib import Path

prototypes = [
    Path(r"C:/Users/admin/.gemini/antigravity/brain/c833b7b8-840e-4dde-a51d-372fc4e4b0a5/.user_uploaded/media_1794683317178_8f3d8454.html"),
    Path(r"C:/Users/admin/.gemini/antigravity/brain/c833b7b8-840e-4dde-a51d-372fc4e4b0a5/.user_uploaded/media_1794683317210_60bd4f36.html"),
    Path(r"C:/Users/admin/.gemini/antigravity/brain/c833b7b8-840e-4dde-a51d-372fc4e4b0a5/.user_uploaded/media_1794683317245_83404717.html"),
    Path(r"C:/Users/admin/.gemini/antigravity/brain/c833b7b8-840e-4dde-a51d-372fc4e4b0a5/.user_uploaded/media_1794683317277_cc961398.html"),
]

master_words = {}
master_phrases = {}

for p in prototypes:
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    
    # Extract word dict entries: "word":{h:"...", p:"..."}
    patt_word = r'["\']([a-zA-Z0-9_\-\.\'\s]+)["\']\s*:\s*\{\s*h\s*:\s*["\']([^"\']+)["\'](?:\s*,\s*p\s*:\s*["\']([^"\']*)["\'])?\s*\}'
    for m in re.finditer(patt_word, text):
        w = m.group(1).lower().strip()
        h = m.group(2).strip()
        pr = (m.group(3) or "").strip()
        if w and (w not in master_words or not master_words[w]["p"]):
            master_words[w] = {"h": h, "p": pr}
            
    # Extract phrases PH = { "English sentence": "हिंदी वाक्य" }
    patt_ph = r'["\']([^"\'\n]{10,250})["\']\s*:\s*["\']([^"\'\n]{10,350})["\']'
    for m in re.finditer(patt_ph, text):
        en = m.group(1).strip()
        hi = m.group(2).strip()
        # check if it looks like English -> Devanagari
        if re.search(r'[a-zA-Z]', en) and re.search(r'[\u0900-\u097F]', hi):
            master_phrases[en] = hi

print(f"Total Unique Master Words: {len(master_words)}")
print(f"Total Unique Master Phrases: {len(master_phrases)}")

out_words = Path("scripts/master_words_lle.json")
out_words.write_text(json.dumps(master_words, ensure_ascii=False, indent=2), encoding="utf-8")

out_phrases = Path("scripts/master_phrases_lle.json")
out_phrases.write_text(json.dumps(master_phrases, ensure_ascii=False, indent=2), encoding="utf-8")
print("Saved master LLE dictionaries successfully.")
