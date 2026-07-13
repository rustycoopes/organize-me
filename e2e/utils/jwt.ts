import crypto from 'node:crypto';

/**
 * Mints a JWT that looks like one the Host would issue, without knowing the real signing secret
 * (Slice R10, #165). Used only to prove Event Creator's JWT-trust boundary rejects a token it
 * didn't actually sign - `organizeme_chrome.jwt_verify.verify_token` (HS256, audience
 * "fastapi-users:auth") will fail signature verification against any secret other than the real
 * one, so a throwaway secret here produces exactly the "tampered signature" case without ever
 * touching JWT_SECRET_QA.
 */
function base64url(input: string): string {
  return Buffer.from(input).toString('base64url');
}

export function forgeToken(
  payload: Record<string, unknown>,
  secret = 'not-the-real-signing-secret',
): string {
  const header = { alg: 'HS256', typ: 'JWT' };
  const signingInput = `${base64url(JSON.stringify(header))}.${base64url(JSON.stringify(payload))}`;
  const signature = crypto
    .createHmac('sha256', secret)
    .update(signingInput)
    .digest('base64url');
  return `${signingInput}.${signature}`;
}

/** A token shaped like a valid Host-issued one (aud + exp set correctly) but signed with the
 * wrong secret - exercises the "tampered signature" trust-boundary case. */
export function tamperedToken(sub = '11111111-1111-1111-1111-111111111111'): string {
  return forgeToken({
    sub,
    aud: 'fastapi-users:auth',
    exp: Math.floor(Date.now() / 1000) + 3600,
  });
}
