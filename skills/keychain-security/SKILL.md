---
name: keychain-security
description: >
  Keychain and credential management patterns for UnleashedMail. Activates when
  working with OAuth tokens, stored credentials, encryption keys, or any
  Security.framework / Keychain Services code.
allowed-tools: Read, Write, Edit, Grep, Glob
---

# Keychain Security — UnleashedMail

## Architecture (how it actually works)

Every OAuth credential is its **own macOS Keychain item** (`kSecClassGenericPassword`), stored and
read through the shared **`KeychainManager`** wrapper. There is **no** master-key-encrypted
credential file or SQLite credential store for tokens — do not create one. The SQLCipher database
key is a **separate** Keychain item that encrypts the email database only and never touches the
tokens.

```
macOS Keychain (kSecClassGenericPassword, via KeychainManager)
├── service "com.unleashedmail.auth"            — Gmail, per account:
│     "<email>:accessToken" / ":refreshToken" / ":tokenExpiry" / ":userEmail"
├── service "com.unleashedmail.microsoft.auth"  — Microsoft, per account:
│     "<email>:accessToken" / ":refreshToken" / ":tokenExpiry" / ":accountId" / ":mailboxEmail"
│     (+ MSAL keeps its own Keychain-backed cache via cacheConfig.keychainSharingGroup)
└── service "com.unleashedmail.database"         — SQLCipher key (SEPARATE concern):
      "encryption_key_v1" (+ "cipher_salt_v1"); encrypts the email DB only, not the tokens
```

Three cleanly separated Keychain services; no single key wraps the credentials.

## Use `KeychainManager` — never hand-roll Keychain access

Route ALL Keychain access through the shared `KeychainManager` (`KeychainManager.swift` + its
extensions). Do not write your own `SecItem*` wrapper — `KeychainManager` already handles the
subtleties correctly:

- `save(_:service:account:synchronizable:)`, `loadString(...)`, `loadData(...)`, `delete(...)`, `exists(...)`, `listAccountKeys(...)`.
- `kSecClassGenericPassword` via `SecItemAdd` / `SecItemCopyMatching` / `SecItemDelete`; it does **delete-then-add** on update (not `SecItemUpdate`).
- Enforces `synchronizable: false` (never syncs to iCloud Keychain) and defaults to `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`.
- Resolves the entitled keychain access group; supports biometric-gated items (`LAContext` / `SecAccessControl`); retries transient `errSec*` statuses.
- Auto-routes to an **in-memory store under XCTest** (`TestEnvironment.isRunningTests`) — call `KeychainManager.resetInMemoryStore()` in `tearDown()`; never call `SecItem*` directly in tests.

```swift
// Save / load / delete a per-account token (Gmail example)
try KeychainManager.save(accessToken, service: "com.unleashedmail.auth",
                         account: "\(email):accessToken", synchronizable: false)
let token = try KeychainManager.loadString(service: "com.unleashedmail.auth",
                                           account: "\(email):accessToken")
try KeychainManager.delete(service: "com.unleashedmail.auth",
                           account: "\(email):accessToken")
```

Gmail token I/O lives in `AuthService+Keychain.swift` / `AuthService+TokenExpiry.swift`; Microsoft
in `MicrosoftAuthService+AccountManagement.swift` / `MicrosoftAuthService+Helpers.swift`. Follow
those; don't reinvent them.

## SQLCipher database key (separate subsystem)

The email database's encryption key is owned by `EncryptionKeyManager` — Keychain service
`com.unleashedmail.database`, account `encryption_key_v1` (+ `cipher_salt_v1`). It is a 256-bit key
from `SecRandomCopyBytes`, used only as the SQLCipher `PRAGMA key`. Keep it distinct from OAuth
credentials — it never encrypts or wraps the tokens.

## Entitlements

`keychain-access-groups` in the app entitlements gates the shared access group; `KeychainManager`
resolves the entitled group at runtime. Editing entitlements is a project-structure change —
**ask before modifying** (per CLAUDE.md's "Ask Before Modifying").

## Security Rules

1. **Never log token values** — log metadata (expiry, scope) only; use `PIIRedactor`.
2. **`kSecAttrAccessibleWhenUnlockedThisDeviceOnly` + `synchronizable: false`** — tokens never sync via iCloud Keychain (`KeychainManager` enforces both).
3. **Wipe every per-account key on sign-out** — delete each `<email>:…` item for the account (Gmail + Microsoft services).
4. **Token refresh is atomic** — persist the new access/refresh/expiry together; on failure, leave the stored set unchanged.
5. **Never store tokens in UserDefaults, plist files, a credential file, or unencrypted/SQLCipher GRDB columns** — tokens live only as individual Keychain items.
6. **Don't hand-roll Keychain code or a master-key credential store** — use `KeychainManager`; the SQLCipher key (`EncryptionKeyManager`) is a separate concern.
