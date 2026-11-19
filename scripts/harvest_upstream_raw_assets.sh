#!/usr/bin/env bash
# G74: AASHA Upstream Raw Source & High-Res Multimedia Asset Harvester
# Run on Local PC (Git Bash / WSL) or Google Colab Online Runner (where outbound internet is enabled).
# Separates MIT/BSD/CC-BY-4.0 permissive repos from GPL-3.0 isolated repos into raw_source_vault/.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT_MIT="$ROOT_DIR/raw_source_vault/mit_bsd_ccby"
VAULT_GPL="$ROOT_DIR/raw_source_vault/gpl_isolated"
TMP_CLONE="$ROOT_DIR/.tmp_upstream_clones"

mkdir -p "$VAULT_MIT"/{packages/sims,packages/games,packages/quiz-widgets,assets/sprites-3d-shaders,assets/video-media,assets/audio-phonics,assets/svg-vectors}
mkdir -p "$VAULT_GPL"/{gcompris,sugarizer}
mkdir -p "$TMP_CLONE"

clone_if_missing() {
  local url="$1"
  local dest="$2"
  if [ ! -d "$dest/.git" ]; then
    echo "[HARVEST] Cloning $url -> $dest"
    git clone --depth 1 "$url" "$dest"
  else
    echo "[HARVEST] Updating $dest"
    git -C "$dest" pull --ff-only || true
  fi
}

# 1. Permissive MIT / BSD-3-Clause / CC-BY-4.0 Repositories
clone_if_missing "https://github.com/Khan/perseus.git" "$TMP_CLONE/perseus"
clone_if_missing "https://github.com/scratchfoundation/scratch-gui.git" "$TMP_CLONE/scratch-gui"
clone_if_missing "https://github.com/phetsims/scenery.git" "$TMP_CLONE/phet-scenery"
clone_if_missing "https://github.com/phetsims/circuit-construction-kit-dc.git" "$TMP_CLONE/phet-cck-dc"
clone_if_missing "https://github.com/phetsims/fractions-intro.git" "$TMP_CLONE/phet-fractions-intro"
clone_if_missing "https://github.com/pixijs/pixijs.git" "$TMP_CLONE/pixijs"
clone_if_missing "https://github.com/liabru/matter-js.git" "$TMP_CLONE/matter-js"

# Extract Perseus Interactive Widgets (MIT)
if [ -d "$TMP_CLONE/perseus/packages/perseus/src/widgets" ]; then
  cp -r "$TMP_CLONE/perseus/packages/perseus/src/widgets" "$VAULT_MIT/packages/quiz-widgets/perseus-widgets"
fi

# Extract Scratch Sprite/Costume/Backdrop Libraries (BSD-3-Clause)
if [ -d "$TMP_CLONE/scratch-gui/src/lib/libraries" ]; then
  cp -r "$TMP_CLONE/scratch-gui/src/lib/libraries" "$VAULT_MIT/packages/games/scratch-libraries"
fi

# Extract PhET Scenery + Sim Source + Hindi Strings + Sounds + Images
for sim in phet-cck-dc phet-fractions-intro; do
  if [ -d "$TMP_CLONE/$sim/js" ]; then
    mkdir -p "$VAULT_MIT/packages/sims/$sim"
    cp -r "$TMP_CLONE/$sim/js" "$VAULT_MIT/packages/sims/$sim/"
    [ -d "$TMP_CLONE/$sim/images" ] && cp -r "$TMP_CLONE/$sim/images" "$VAULT_MIT/assets/sprites-3d-shaders/$sim-images"
    [ -d "$TMP_CLONE/$sim/sounds" ] && cp -r "$TMP_CLONE/$sim/sounds" "$VAULT_MIT/assets/audio-phonics/$sim-sounds"
    [ -d "$TMP_CLONE/$sim/strings" ] && cp -r "$TMP_CLONE/$sim/strings" "$VAULT_MIT/packages/sims/$sim/"
  fi
done

# 2. Copyleft GPL-3.0 / Apache-2.0 Repositories (Strictly Isolated)
clone_if_missing "https://github.com/gcompris/GCompris-qt.git" "$VAULT_GPL/gcompris/GCompris-qt"
clone_if_missing "https://github.com/llaske/sugarizer.git" "$VAULT_GPL/sugarizer/sugarizer"

echo "[HARVEST] Completed raw source & multimedia extraction into raw_source_vault/."
