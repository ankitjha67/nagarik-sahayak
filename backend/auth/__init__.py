"""Authentication, sessions and authorisation.

Design, in one paragraph. A citizen proves possession of a phone number with
a one-time code (hashed, single-use, attempt-limited, delivered through a
pluggable SMS provider). They receive a short-lived signed access token and an
opaque rotating refresh token; the refresh token is stored hashed and reuse of
a rotated-out token revokes the whole session (token theft). Every request is
checked by one dependency with one rule: a request that names a user must be
authenticated as that user, or by a role allowed to act for them. Roles are
citizen, operator (a CSC/VLE worker acting with the citizen's recorded
consent), reviewer and admin; admins need TOTP. Demo placeholders exist only in
a demo build and can never collide with a real account.

Modules:
  settings  - every tunable, read from the environment on demand
  totp      - RFC 6238 one-time passwords for admin MFA (no dependency)
  store     - session / OTP / consent / audit storage: Mongo, or memory in tests
  tokens    - access tokens, refresh rotation, session revocation
  otp       - hashed one-time codes with lockout
  sms       - delivery providers (log, MSG91, Twilio, generic webhook)
  audit     - hash-chained record of authentication events
  deps      - FastAPI dependencies: principal, enforcement, subject binding
"""
