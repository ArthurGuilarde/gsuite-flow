# Core adapter contract v1
**Proposed integration contract, not an assertion that these endpoints already exist.** Implement this contract in the Core or change only the adapter to match an agreed existing API before rollout.
The app never reads Core, Billing or Authentik databases. OIDC login alone does not grant app or tenant access.

## POST /v1/authorize
Header: `Authorization: Bearer <user access token>`.
Request:
```json
{"app_id":"minha-app","tenant_id":"3e63cdf2-64d8-4752-82b9-a3cf8e5ba8bf","permission":"read"}
```
Response 200:
```json
{"sub":"stable-idp-subject","tenant_id":"3e63cdf2-64d8-4752-82b9-a3cf8e5ba8bf","app_id":"minha-app","allowed":true,"permissions":["access","read","write"],"features":[]}
```
Core must validate issuer, signature, expiry and app-specific audience; resolve the authenticated subject from the token, never from request data; verify active tenant membership, application entitlement and required permission. Membership revocation denies the next API request. Subscription policy, including any grace period, belongs to the Core. Product-specific membership rules belong to the Core and must be documented in project-context.md.
The adapter checks returned sub, tenant_id, app_id, allowed and access + requested permission. Missing/malformed grants or network errors deny access. There is no positive authorization cache in v1. Core availability is therefore required for domain requests.
401: invalid identity; 403: membership/entitlement/permission denied; 5xx/timeouts: app returns 503.

## GET /v1/me/tenants?app_id=minha-app
Same bearer authentication. Return only workspaces the subject can access for this app:
```json
{"tenants":[{"id":"3e63cdf2-64d8-4752-82b9-a3cf8e5ba8bf","name":"Meu espaço"}]}
```
The frontend-selected X-Tenant-ID is untrusted until POST /v1/authorize succeeds.

## Identity provider
Use a confidential OIDC provider for each app, Authorization Code + PKCE S256, exact callback `<PUBLIC_URL>/auth/callback`, issuer-specific discovery and JWKS. Access token must be RS256 with configured audience, iss, sub, exp and iat. ID token is validated by Authlib for nonce, signature and claims; its subject must match the independently validated access token.
No universal audience is assumed. Configure the Core to accept only tokens for registered applications.
No SDK dependency is invented: this adapter can be replaced by suite-auth-sdk once that package and contract actually exist.
No refresh token is requested or persisted: expired access tokens require login again; IdP SSO can make this transparent. Global IdP logout is separate from the implemented local application logout.
