# Rule: Secret Hygiene

**Scope:** everywhere, always, in every language. This is the rule most likely to cause real-world harm
if violated.

## What is a secret

Anything that authenticates, authorizes, or can be used to impersonate.

For code purposes, treat any field whose name matches `*_token`, `*_secret`,
`*_password`, `*_key`, or `*_credential` as a secret.

## Where secrets live

| Location | Secrets allowed? |
|---|---|
| `.env` | ✅ Yes (primary store) |
| OS environment variables | ✅ Yes |
| A secret manager (Vault, cloud KMS/Secrets Manager, CI secret store) | ✅ Yes |
| Source code | ❌ Never, including tests |
| Git history | ❌ Never |
| Commit messages, PR descriptions, logs | ❌ Never |

Tests and gates read secrets from `.env` / the process environment / the project's secret manager at
runtime — never hardcode a value in a test or fixture.

## Rules for code (illustrated in Python; the same rule applies in every language)

### Never log a secret

```python
# BAD
log.info("api_call", token=access_token)

# GOOD
log.info("api_call", token_present=bool(access_token))
```

### Never include secrets in exception messages

```python
# BAD
raise ValueError(f"Auth failed with token {token}")

# GOOD
raise ValueError("Auth failed. Check your API key in .env.")
```

### Never print, log, or serialize a config object that may contain secrets

Use whatever secret-typed value your language/framework offers (e.g. Pydantic's `SecretStr`, a
`sensitive`-tagged struct field, a `SecureString`) so a naive print/log/serialize of the config never
leaks the raw value. Extract the raw value only at the boundary where it's actually used.

## Rules for `.gitignore`

The repo's `.gitignore` is the enforcement point. If you introduce a new secret-bearing file location,
**add it to `.gitignore` before creating the file**.

## Rules for commits

Before every commit involving new or changed files:

1. Scan the diff for strings that look like tokens (length > 20, mix of alphanumerics, common prefixes
   like `sk-`, `gsk_`, `ghp_`).
2. If anything matches, **stop**. Do not include in the commit. Rotate the secret if it was real.
3. `git diff --cached` is your friend.

## Rules for AI agents

- **Load secrets programmatically, never echo them.** The build and tests load secrets from `.env` (or
  the project's config loader / process env) programmatically — that is expected. Do not echo or paste
  raw `.env` values into responses or logs. When you must confirm a secret is set, confirm by presence
  only (a bool), never by value.
- **Never echo, print, or paste a secret value** into your response.
- **Never commit a file that contains a secret** even if the user asks. Push back, rotate, continue.
- **When intake requests API keys or credentials, instruct the user to put them in `.env`** (gitignored)
  — never accept secrets pasted into chat or committed to source.

## If a secret leaks

1. Rotate the secret immediately at the provider.
2. Update the relevant `.env` (or secret manager entry) with the new value.
3. Purge from git history if committed: `git filter-repo` or `bfg`. Force-push with operator approval.
4. Note the incident in the commit message without repeating the leaked value.
