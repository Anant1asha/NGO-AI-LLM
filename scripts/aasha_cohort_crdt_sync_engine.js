/**
 * AASHA Cycle 4 Centre Cohort CRDT Offline Sync Engine & Facilitator Diagnostic Aggregator (JS Parity)
 */
class CohortCRDTProgressMergerJS {
  static mergeTwoStates(a, b) {
    const replicas = new Set([...Object.keys(a.replica_attempts || {}), ...Object.keys(b.replica_attempts || {})]);
    const mergedAttempts = {};
    for (const r of Array.from(replicas).sort()) {
      mergedAttempts[r] = Math.max(a.replica_attempts?.[r] || 0, b.replica_attempts?.[r] || 0);
    }
    return {
      student_id: a.student_id,
      concept_id: a.concept_id,
      mastery_score: Math.max(a.mastery_score || 0, b.mastery_score || 0),
      replica_attempts: mergedAttempts,
      hlc_timestamp_ms: Math.max(a.hlc_timestamp_ms || 0, b.hlc_timestamp_ms || 0),
    };
  }
}

class FacilitatorDiagnosticAggregatorJS {
  static needsInterventionPod(struggleRatio, strugglingCount) {
    return struggleRatio >= 0.3 || strugglingCount >= 2;
  }
}

module.exports = {
  CohortCRDTProgressMergerJS,
  FacilitatorDiagnosticAggregatorJS,
};
