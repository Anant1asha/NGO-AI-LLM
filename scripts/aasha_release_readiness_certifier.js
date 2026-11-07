/**
 * AASHA Cycle 4 Phase F/G 10-Rule QA Release Certifier & Cryptographic Bundle Signer (JS Parity)
 */
const crypto = require("crypto");

class TenRuleQAReleaseCertifierJS {
  static hasExternalCdnLeak(html = "") {
    return /<(?:script|link|img)\b[^>]*?\b(?:src|href)\s*=\s*['"]https?:\/\//i.test(html);
  }
}

class CryptographicReleaseBundleSignerJS {
  static signPayload(payloadSha256, key = "EPHEMERAL_KEY") {
    return crypto.createHmac("sha256", key).update(payloadSha256).digest("hex");
  }
}

module.exports = {
  TenRuleQAReleaseCertifierJS,
  CryptographicReleaseBundleSignerJS,
};
