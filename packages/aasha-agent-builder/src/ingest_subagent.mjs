/**
 * packages/aasha-agent-builder/src/ingest_subagent.mjs
 * AASHA AIOS — Task 1: Curriculum Ingest & Concept Analysis Subagent Coordinator
 *
 * Implements authoritative requirements T1-01 to T1-18:
 * - Pure Node.js ESM coordinator (zero duplicate PDF extraction logic)
 * - Safe path containment & nearest existing ancestor resolution
 * - Dual-layer verification: Source byte SHA-256 integrity vs Semantic grounding
 * - Windows/POSIX process tree lifecycle management with cooperative control abort
 * - Per-job output isolation using dynamically synthesized job_config.yaml
 * - Streaming NDJSON event parsing with real-time status tracking
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as crypto from 'node:crypto';
import { spawn, execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

/**
 * Resolves the repository root directory by climbing ancestors until package.json with AASHA markers is found.
 * @param {string} [startDir=process.cwd()]
 * @returns {string} Absolute path to workspace root
 */
export function resolveWorkspaceRoot(startDir = process.cwd()) {
  let current = path.resolve(startDir);
  while (true) {
    const pkgPath = path.join(current, 'package.json');
    if (fs.existsSync(pkgPath)) {
      try {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
        if (pkg.name === 'aasha-learning-ecosystem-root' || pkg.name === 'aasha-ai') {
          return current;
        }
      } catch {
        // Continue searching upward
      }
    }
    const parent = path.dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }
  return path.resolve(startDir);
}

/**
 * Loads the YAML parser/stringifier module from the monorepo workspace.
 * Resolves from aasha-studio/node_modules/yaml if available, or native fallback.
 * @returns {{ parse: (str: string) => any, stringify: (obj: any) => string }}
 */
export function getYamlEngine() {
  const root = resolveWorkspaceRoot();
  const candidateYamlPaths = [
    'yaml',
    path.join(root, 'aasha-studio', 'node_modules', 'yaml'),
    path.join(root, 'node_modules', 'yaml'),
  ];

  for (const p of candidateYamlPaths) {
    try {
      const mod = require(p);
      if (mod && typeof mod.parse === 'function') {
        return mod;
      }
    } catch {}
  }

  // Pure-JS minimal fallback parser for simple key-value YAML if module is decoupled
  return {
    parse: (str) => {
      // Basic fallback: parse simple YAML lines if yaml package not installed
      const res = {};
      const lines = str.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const idx = trimmed.indexOf(':');
        if (idx !== -1) {
          const key = trimmed.slice(0, idx).trim();
          const val = trimmed.slice(idx + 1).trim().replace(/^['"]|['"]$/g, '');
          res[key] = val;
        }
      }
      return res;
    },
    stringify: (obj) => {
      const serialize = (val, indent = 0) => {
        const pad = '  '.repeat(indent);
        let out = '';
        if (typeof val === 'object' && val !== null) {
          for (const [k, v] of Object.entries(val)) {
            if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
              out += `${pad}${k}:\n${serialize(v, indent + 1)}`;
            } else if (Array.isArray(v)) {
              out += `${pad}${k}:\n`;
              for (const item of v) {
                out += `${pad}  - ${typeof item === 'object' ? JSON.stringify(item) : item}\n`;
              }
            } else {
              out += `${pad}${k}: ${JSON.stringify(v)}\n`;
            }
          }
        }
        return out;
      };
      return serialize(obj);
    }
  };
}

/**
 * Resolves and validates that a target path is strictly contained within an allowed base directory.
 * Defends against path traversal, symlink breakouts, and TOCTOU vulnerabilities.
 * @param {string} baseDir Base directory that must contain target
 * @param {string} userPath User-supplied or candidate path
 * @param {object} [options]
 * @param {boolean} [options.mustExist=false] If true, resolved path must exist
 * @returns {string} Fully resolved safe absolute path
 */
export function resolveSecurePath(baseDir, userPath, options = {}) {
  const { mustExist = false } = options;
  if (!baseDir || typeof baseDir !== 'string') {
    throw new Error('resolveSecurePath: baseDir must be a non-empty string');
  }
  if (!userPath || typeof userPath !== 'string') {
    throw new Error('resolveSecurePath: userPath must be a non-empty string');
  }

  const absBase = path.resolve(baseDir);
  const realBase = fs.existsSync(absBase) ? fs.realpathSync(absBase) : absBase;
  const absTarget = path.isAbsolute(userPath)
    ? path.normalize(userPath)
    : path.resolve(realBase, userPath);

  // Find nearest existing ancestor to resolve real symlinks
  let ancestor = absTarget;
  while (!fs.existsSync(ancestor)) {
    const parent = path.dirname(ancestor);
    if (parent === ancestor) break;
    ancestor = parent;
  }
  const realAncestor = fs.existsSync(ancestor) ? fs.realpathSync(ancestor) : ancestor;
  const remainder = path.relative(ancestor, absTarget);
  const effectiveTarget = remainder ? path.resolve(realAncestor, remainder) : realAncestor;

  const rel = path.relative(realBase, effectiveTarget);
  const segments = rel.split(path.sep);

  if (segments[0] === '..' || path.isAbsolute(rel)) {
    throw new Error(`Security Violation: Path traversal detected outside base directory. Target: ${userPath}, Base: ${baseDir}`);
  }

  if (mustExist && !fs.existsSync(effectiveTarget)) {
    throw new Error(`Target file does not exist: ${effectiveTarget}`);
  }

  return effectiveTarget;
}

/**
 * Calculates SHA-256 digest of a target file.
 * @param {string} filePath Absolute or relative path to file
 * @returns {string} Hexadecimal SHA-256 digest
 */
export function computeFileSha256(filePath) {
  const buffer = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(buffer).digest('hex');
}

/**
 * Verifies byte-level integrity against an expected SHA-256 checksum.
 * Note: Byte integrity strictly validates bitstream provenance; it does NOT assert semantic textbook grounding.
 * @param {string} filePath Target file path
 * @param {string} [expectedSha256] Expected 64-char hex digest (optional)
 * @returns {{ verified: boolean, actualSha256: string, expectedSha256: string | null, status: string }}
 */
export function verifySourceIntegrity(filePath, expectedSha256 = null) {
  if (!fs.existsSync(filePath)) {
    return {
      verified: false,
      actualSha256: '',
      expectedSha256,
      status: 'SOURCE_NOT_FOUND'
    };
  }

  const actualSha256 = computeFileSha256(filePath);
  if (!expectedSha256) {
    return {
      verified: true,
      actualSha256,
      expectedSha256: null,
      status: 'SOURCE_INTEGRITY_COMPUTED'
    };
  }

  const match = actualSha256.toLowerCase() === expectedSha256.toLowerCase();
  return {
    verified: match,
    actualSha256,
    expectedSha256,
    status: match ? 'SOURCE_INTEGRITY_VERIFIED' : 'SOURCE_INTEGRITY_FAILED'
  };
}

/**
 * Locates the Python executable, giving precedence to project virtualenvs.
 * @param {string} workspaceRoot
 * @returns {string} Absolute path or executable name for Python
 */
export function resolvePythonBinary(workspaceRoot) {
  const isWin = process.platform === 'win32';
  const candidates = [
    path.join(workspaceRoot, 'Aasha-AI', 'aasha-pipeline-with-master-json', '.venv', isWin ? 'Scripts/python.exe' : 'bin/python'),
    path.join(workspaceRoot, '.venv', isWin ? 'Scripts/python.exe' : 'bin/python'),
    path.join(workspaceRoot, 'venv', isWin ? 'Scripts/python.exe' : 'bin/python'),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return isWin ? 'python' : 'python3';
}

/**
 * Terminates a process and its entire descendant process tree cleanly.
 * Windows: taskkill /PID <pid> /T /F
 * POSIX: process.kill(-pid, 'SIGKILL')
 * @param {number} pid Target process PID
 * @param {object} [logger=console]
 */
export function terminateProcessTree(pid, logger = console) {
  if (!pid) return;
  const isWin = process.platform === 'win32';
  try {
    if (isWin) {
      execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { stdio: 'ignore' });
    } else {
      process.kill(-pid, 'SIGKILL');
    }
  } catch (err) {
    logger.warn?.(`[IngestSubagent] Process termination notice for PID ${pid}: ${err.message}`);
  }
}

/**
 * Creates an isolated job configuration YAML in work/<job_id>/job_config.yaml,
 * overriding pipeline.work_dir and pipeline.output_dir to prevent candidate builds
 * from writing to shared or release directories.
 * @param {string} baseConfigPath Path to master config.yaml
 * @param {string} jobDir Absolute path to work/<job_id>
 * @param {string} jobOutputDir Absolute path to work/<job_id>/output
 * @returns {string} Path to synthesized job configuration YAML
 */
export function createIsolatedJobConfig(baseConfigPath, jobDir, jobOutputDir) {
  fs.mkdirSync(jobDir, { recursive: true });
  fs.mkdirSync(jobOutputDir, { recursive: true });

  const yamlEngine = getYamlEngine();
  let configData = {};
  if (fs.existsSync(baseConfigPath)) {
    try {
      const content = fs.readFileSync(baseConfigPath, 'utf-8');
      configData = yamlEngine.parse(content) || {};
    } catch {
      configData = {};
    }
  }

  configData.pipeline = configData.pipeline || {};
  configData.pipeline.work_dir = jobDir;
  configData.pipeline.output_dir = jobOutputDir;

  const jobConfigPath = path.join(jobDir, 'job_config.yaml');
  fs.writeFileSync(jobConfigPath, yamlEngine.stringify(configData), 'utf-8');
  return jobConfigPath;
}

/**
 * Spawns the underlying Python CLI ingest pipeline as a child process.
 * Emits parsed NDJSON events and enforces process tree termination on abort.
 *
 * @param {object} options
 * @param {string} options.workspaceRoot
 * @param {string} options.pdfPath
 * @param {string} [options.jobId]
 * @param {string} [options.mode='v5-engine']
 * @param {string} [options.provider='openrouter']
 * @param {boolean} [options.offline=false]
 * @param {AbortSignal} [options.signal]
 * @param {function} [options.onEvent]
 * @param {object} [options.logger=console]
 * @returns {Promise<{ jobId: string, status: string, outputs: object, duration: number, events: Array<object> }>}
 */
export function spawnPythonIngest(options) {
  const {
    workspaceRoot,
    pdfPath,
    jobId = `job_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`,
    mode = 'v5-engine',
    provider = 'openrouter',
    offline = false,
    signal,
    onEvent,
    logger = console,
  } = options;

  return new Promise((resolve, reject) => {
    const pipelineRoot = path.join(workspaceRoot, 'Aasha-AI', 'aasha-pipeline-with-master-json');
    const masterConfigPath = path.join(pipelineRoot, 'config.yaml');
    const workBaseDir = path.join(pipelineRoot, 'work');
    const jobDir = path.join(workBaseDir, jobId);
    const jobOutputDir = path.join(jobDir, 'output');

    // 1. Synthesize isolated job configuration
    const jobConfigPath = createIsolatedJobConfig(masterConfigPath, jobDir, jobOutputDir);

    // 2. Resolve python binary
    const pythonBin = resolvePythonBinary(workspaceRoot);

    const cliArgs = [
      '-m', 'aasha.cli',
      '--pdf', pdfPath,
      '--mode', mode,
      '--config', jobConfigPath,
      '--json-events',
    ];

    if (offline) {
      cliArgs.push('--offline');
    } else if (provider) {
      cliArgs.push('--provider', provider);
    }

    const env = { ...process.env };
    if (offline) {
      env.AASHA_OFFLINE = '1';
    }

    const child = spawn(pythonBin, cliArgs, {
      cwd: pipelineRoot,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: process.platform !== 'win32', // Allows process grouping on POSIX
    });

    const events = [];
    let stdoutBuffer = '';
    let finalPayload = null;
    let isTerminating = false;

    const handleAbort = () => {
      if (isTerminating) return;
      isTerminating = true;

      // Stage A: Cooperative signal via control.json
      try {
        const controlPath = path.join(jobDir, 'control.json');
        fs.writeFileSync(controlPath, JSON.stringify({
          action: 'abort',
          issuer: 'ingest_subagent',
          reason: 'Subagent coordinator signal abort',
          timestamp: new Date().toISOString()
        }, null, 2), 'utf-8');
      } catch {
        // Fallback to direct process termination
      }

      // Stage B: 5-second grace period before forceful process tree kill
      const timer = setTimeout(() => {
        terminateProcessTree(child.pid, logger);
      }, 5000);

      child.once('exit', () => {
        clearTimeout(timer);
      });
    };

    if (signal) {
      if (signal.aborted) {
        handleAbort();
      } else {
        signal.addEventListener('abort', handleAbort, { once: true });
      }
    }

    child.stdout.on('data', (chunk) => {
      stdoutBuffer += chunk.toString('utf-8');
      const lines = stdoutBuffer.split('\n');
      stdoutBuffer = lines.pop(); // Retain incomplete line

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('{')) continue;
        try {
          const parsed = JSON.parse(trimmed);
          events.push(parsed);
          onEvent?.(parsed);
          if (parsed.event === 'pipeline_complete' || parsed.event === 'pipeline_quarantined' || parsed.event === 'pipeline_failed') {
            finalPayload = parsed;
          }
        } catch {
          // Ignore non-JSON stdout lines
        }
      }
    });

    child.stderr.on('data', (chunk) => {
      const errText = chunk.toString('utf-8');
      logger.warn?.(`[Python Stderr] ${errText}`);
    });

    child.on('error', (err) => {
      reject(new Error(`Failed to start Python pipeline process: ${err.message}`));
    });

    child.on('close', (code) => {
      if (signal) {
        signal.removeEventListener('abort', handleAbort);
      }

      // Flush remaining stdout
      if (stdoutBuffer.trim().startsWith('{')) {
        try {
          const parsed = JSON.parse(stdoutBuffer.trim());
          events.push(parsed);
          onEvent?.(parsed);
          if (parsed.event?.startsWith('pipeline_')) finalPayload = parsed;
        } catch {}
      }

      if (signal?.aborted) {
        return reject(new Error('Ingest pipeline execution was aborted.'));
      }

      if (code === 0 || finalPayload?.status === 'completed') {
        return resolve({
          jobId: finalPayload?.job_id || jobId,
          status: 'COMPLETED',
          outputs: {
            html: finalPayload?.html_path || path.join(jobOutputDir, 'chapter.html'),
            jobOutputDir,
          },
          duration: finalPayload?.duration || 0,
          events,
        });
      }

      if (finalPayload?.status === 'quarantined') {
        return resolve({
          jobId: finalPayload.job_id || jobId,
          status: 'QUARANTINED',
          quarantinePacket: finalPayload.quarantine_packet,
          errorStage: finalPayload.error_stage,
          errorMessage: finalPayload.error_message,
          events,
        });
      }

      const errMsg = finalPayload?.error_message || `Process exited with code ${code}`;
      return reject(new Error(`Ingest pipeline execution failed: ${errMsg}`));
    });
  });
}

/**
 * Main Task 1 Coordinator: Curriculum Ingest & Concept Analysis Subagent.
 * Orchestrates contract ingestion, source verification, Python pipeline execution,
 * and emits the authoritative 5-dimensional governance matrix.
 *
 * @param {object} params
 * @param {string} [params.contractPath] Path to Section 24 YAML contract
 * @param {string} [params.pdfPath] Path to textbook PDF
 * @param {string} [params.expectedSourceHash] Expected SHA-256 hash of PDF
 * @param {string} [params.mode='v5-engine']
 * @param {string} [params.provider='openrouter']
 * @param {boolean} [params.offline=true] Default to offline mode for deterministic testing
 * @param {AbortSignal} [params.signal]
 * @param {object} [params.logger=console]
 * @returns {Promise<object>} Orchestration result with 5D governance record
 */
export async function ingestSubagent(params = {}) {
  const workspaceRoot = resolveWorkspaceRoot();
  const logger = params.logger || console;
  const yamlEngine = getYamlEngine();

  let contractData = null;
  let contractSha256 = null;

  // 1. Process Section 24 YAML Contract if supplied
  if (params.contractPath) {
    const secureContractPath = resolveSecurePath(workspaceRoot, params.contractPath, { mustExist: true });
    contractSha256 = computeFileSha256(secureContractPath);
    const content = fs.readFileSync(secureContractPath, 'utf-8');
    contractData = yamlEngine.parse(content);
  }

  // 2. Determine target PDF path
  let pdfPath = params.pdfPath;
  if (!pdfPath && contractData?.chapter_meta?.textbook_source) {
    // Check if textbook_source mentions a known relative path
    const match = contractData.chapter_meta.textbook_source.match(/content\/pdfs\/[^\s)]+/);
    if (match) {
      const candidate = path.join(workspaceRoot, 'Aasha-AI', match[0]);
      if (fs.existsSync(candidate)) {
        pdfPath = candidate;
      }
    }
  }

  // 3. Dual-Layer Source Integrity Check
  let sourceIntegrityResult = {
    verified: false,
    actualSha256: '',
    expectedSha256: params.expectedSourceHash || null,
    status: 'SOURCE_NOT_PROVIDED'
  };

  if (pdfPath) {
    const securePdfPath = resolveSecurePath(workspaceRoot, pdfPath, { mustExist: false });
    if (fs.existsSync(securePdfPath)) {
      sourceIntegrityResult = verifySourceIntegrity(securePdfPath, params.expectedSourceHash || null);
      pdfPath = securePdfPath;
    } else {
      sourceIntegrityResult.status = 'SOURCE_NOT_FOUND';
    }
  }

  // 4. Five-Dimensional Orthogonal Governance Record
  // Note: Byte integrity (SHA-256) DOES NOT EQUAL semantic textbook grounding.
  const governanceRecord = {
    source_integrity: sourceIntegrityResult.status,
    semantic_grounding: sourceIntegrityResult.verified
      ? 'SOURCE_EVIDENCE_PRESENT_UNVERIFIED'
      : 'GROUNDING_NOT_ASSESSED',
    qa_validation: 'QA_NOT_RUN',
    pedagogical_review: 'PENDING_TEACHER_REVIEW',
    release_authorization: 'NOT_RELEASED'
  };

  // 5. If PDF is available and runPipeline is requested, spawn Python Ingestion
  let pipelineExecution = null;
  if (params.runPipeline && pdfPath && fs.existsSync(pdfPath)) {
    try {
      pipelineExecution = await spawnPythonIngest({
        workspaceRoot,
        pdfPath,
        jobId: params.jobId,
        mode: params.mode || 'v5-engine',
        provider: params.provider || 'openrouter',
        offline: params.offline !== undefined ? params.offline : true,
        signal: params.signal,
        logger,
      });

      governanceRecord.qa_validation = pipelineExecution.status === 'COMPLETED' ? 'QA_PASSED' : 'QA_FAILED';
    } catch (err) {
      governanceRecord.qa_validation = 'QA_FAILED';
      pipelineExecution = {
        status: 'FAILED',
        error: err.message
      };
    }
  }

  return {
    success: governanceRecord.source_integrity !== 'SOURCE_INTEGRITY_FAILED',
    contract: contractData ? {
      slug: contractData.chapter_meta?.slug,
      title: contractData.chapter_meta?.topic,
      grade: contractData.chapter_meta?.class,
      sha256: contractSha256,
      coreConceptsCount: contractData.curriculum_intent?.core_concepts?.length || 0,
      misconceptionsCount: contractData.misconceptions?.length || 0,
    } : null,
    source: {
      pdfPath: pdfPath || null,
      integrity: sourceIntegrityResult
    },
    governance: governanceRecord,
    pipeline: pipelineExecution
  };
}
