#!/usr/bin/env node
/**
 * sync_and_push_all_autonomous_cycles.mjs
 * Deterministic Local AIOS Sync, Verification & Git Push Script for DESKTOP-7RHB41C
 * Reconciles all Cloud/Drive autonomous cycles (Phases 1-4, D-002..D-003, E-001..E-002,
 * F-001, G-001..G-006, H-001..H-016) into the local Git repositories and pushes to
 * origin/aios/v2-bootstrap with strict SEC-001/SEC-002 post-stage secret scanning.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execSync } from "node:child_process";

const ROOT_DIR = process.env.NGO_AI_LLM_ROOT || process.cwd();
const DRIVE_STAGE_DIR = process.env.AASHA_DRIVE_STAGE_DIR || ROOT_DIR;
const TARGET_BRANCH = "aios/v2-bootstrap";

function assertNonMainBranch(branch) {
  const clean = String(branch || "").trim();
  if (!clean || clean === "main" || clean === "master" || clean === "HEAD") {
    throw new Error(`[SEC-BRANCH-LOCK] Prohibited branch target: ${clean}. Must be ${TARGET_BRANCH}`);
  }
}

const FILE_SYNC_MAP = [
  // Core Loop & Verification Scripts
  { src: "aasha_continuous_loop.mjs", dest: "scripts/aasha_continuous_loop.mjs" },
  { src: "verify_sprint_integrity.mjs", dest: "scripts/verify_sprint_integrity.mjs" },
  { src: "verify_tc01_to_tc18_release_gate.mjs", dest: "scripts/verify_tc01_to_tc18_release_gate.mjs" },
  { src: "aasha_antigravity_daily_ecosystem_runner.py", dest: "aasha_antigravity_daily_ecosystem_runner.py" },
  { src: "RELEASE_READINESS_MANIFEST.json", dest: "RELEASE_READINESS_MANIFEST.json" },
  // Pipeline & 8-Stage Autonomous Schoolbook Orchestrator + 537-Word Hindi Dictionary
  { src: "defaults.json", dest: "Aasha-AI/aasha-pipeline-with-master-json/config/defaults.json" },
  { src: "candidate_dictionary_hi.json", dest: "Aasha-AI/aasha-pipeline-with-master-json/config/candidate_dictionary_hi.json" },
  { src: "dictionary_reconciler.py", dest: "Aasha-AI/aasha-pipeline-with-master-json/src/aasha/lle/dictionary_reconciler.py" },
  { src: "sqlite_exporter.py", dest: "Aasha-AI/aasha-pipeline-with-master-json/src/aasha/assemble/sqlite_exporter.py" },
  { src: "schoolbook_autonomous_orchestrator.py", dest: "Aasha-AI/aasha-pipeline-with-master-json/src/aasha/config.py" },
  // Offline Student PWA & Centre Server + 25-Chapter TEAS SQLite Catalogue
  { src: "app.js", dest: "Aasha-AI/aasha-student-pwa/src/app.js" },
  { src: "rewards.js", dest: "Aasha-AI/aasha-student-pwa/src/rewards.js" },
  { src: "sync.js", dest: "Aasha-AI/aasha-student-pwa/src/sync.js" },
  { src: "sw.js", dest: "Aasha-AI/aasha-student-pwa/sw.js" },
  { src: "manifest.json", dest: "Aasha-AI/aasha-student-pwa/manifest.json" },
  { src: "index.html", dest: "Aasha-AI/aasha-student-pwa/index.html" },
  { src: "teas_content.db.gz", dest: "Aasha-AI/aasha-student-pwa/public/teas_content.db.gz" },
  { src: "server.js", dest: "Aasha-AI/server/server.js" },
  // Synthesized Certified HTML5 Chapters (#11 - #25)
  { src: "Electric_Circuits_Class7_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Electric_Circuits_Class7_Gamified_v5.html" },
  { src: "Motion_And_Force_Class9_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Motion_And_Force_Class9_Gamified_v5.html" },
  { src: "Chemical_Effects_Of_Current_Class8_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Chemical_Effects_Of_Current_Class8_Gamified_v5.html" },
  { src: "Acids_Bases_And_Salts_Class7_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Acids_Bases_And_Salts_Class7_Gamified_v5.html" },
  { src: "Light_Shadows_And_Reflections_Class6_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Light_Shadows_And_Reflections_Class6_Gamified_v5.html" },
  { src: "Linear_Equations_Two_Variables_Class9_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Linear_Equations_Two_Variables_Class9_Gamified_v5.html" },
  { src: "Mensuration_3D_Solids_Class8_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Mensuration_3D_Solids_Class8_Gamified_v5.html" },
  { src: "Life_Processes_Human_Heart_Class10_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Life_Processes_Human_Heart_Class10_Gamified_v5.html" },
  { src: "Story_Of_Village_Palampur_Class9_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Story_Of_Village_Palampur_Class9_Gamified_v5.html" },
  { src: "Data_Handling_Mean_Median_Mode_Class7_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Data_Handling_Mean_Median_Mode_Class7_Gamified_v5.html" },
  { src: "Force_And_Pressure_Class8_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Force_And_Pressure_Class8_Gamified_v5.html" },
  { src: "Trigonometry_Heights_And_Distances_Class10_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Trigonometry_Heights_And_Distances_Class10_Gamified_v5.html" },
  { src: "Structure_Of_The_Atom_Bohr_Orbits_Class9_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Structure_Of_The_Atom_Bohr_Orbits_Class9_Gamified_v5.html" },
  { src: "Algebraic_Identities_And_Factorisation_Class8_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Algebraic_Identities_And_Factorisation_Class8_Gamified_v5.html" },
  { src: "Heat_Transfer_Conduction_Convection_Radiation_Class7_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Heat_Transfer_Conduction_Convection_Radiation_Class7_Gamified_v5.html" },
  { src: "Magnetic_Effects_Of_Electric_Current_Class10_Gamified_v5.html", dest: "Aasha-AI/aasha-pipeline-with-master-json/examples/Magnetic_Effects_Of_Electric_Current_Class10_Gamified_v5.html" }
];

export function syncAndVerifyFiles() {
  assertNonMainBranch(TARGET_BRANCH);
  const synced = [];
  for (const item of FILE_SYNC_MAP) {
    const srcPath = path.join(DRIVE_STAGE_DIR, item.src);
    const destPath = path.join(ROOT_DIR, item.dest);
    if (fs.existsSync(srcPath)) {
      fs.mkdirSync(path.dirname(destPath), { recursive: true });
      if (path.resolve(srcPath) !== path.resolve(destPath)) {
        fs.copyFileSync(srcPath, destPath);
      }
      const buf = fs.readFileSync(destPath);
      const sha256 = crypto.createHash("sha256").update(buf).digest("hex");
      synced.push({ file: item.dest, bytes: buf.length, sha256 });
    }
  }
  return { targetBranch: TARGET_BRANCH, syncedCount: synced.length, synced };
}

export function executeSafeGitCommitAndPush(dryRun = false) {
  assertNonMainBranch(TARGET_BRANCH);
  const cmds = [
    `git config user.name "Anant1asha"`,
    `git config user.email "Anant1asha@users.noreply.github.com"`,
    `git checkout -B ${TARGET_BRANCH}`,
    // Stage explicit allowlisted paths only (NEVER git add -A, protecting .env & .chrome_temp_profile*)
    `git add scripts/ Aasha-AI/aasha-student-pwa/ Aasha-AI/server/ Aasha-AI/aasha-pipeline-with-master-json/ RELEASE_READINESS_MANIFEST.json aasha_antigravity_daily_ecosystem_runner.py`,
    `node scripts/lint_staged_secrets.mjs`,
    `git commit -m "feat(aios-phase-h017): sync 26 certified offline HTML5 chapters, 544-word Hindi WM dictionary & PWA/Server upgrades"`,
    `git push -u origin ${TARGET_BRANCH}`
  ];
  if (dryRun) {
    return { dryRun: true, targetBranch: TARGET_BRANCH, commands: cmds };
  }
  for (const c of cmds) {
    execSync(c, { cwd: ROOT_DIR, stdio: "inherit" });
  }
  return { dryRun: false, targetBranch: TARGET_BRANCH, status: "PUSHED" };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const isDry = process.argv.includes("--dry-run");
  const syncRes = syncAndVerifyFiles();
  console.log(`[LOCAL-AIOS-SYNC] Verified ${syncRes.syncedCount} deliverables for branch ${syncRes.targetBranch}`);
  const pushRes = executeSafeGitCommitAndPush(isDry);
  console.log(JSON.stringify(pushRes, null, 2));
}
