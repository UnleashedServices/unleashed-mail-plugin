---
name: keychain-security
description: >
  Keychain and credential management patterns for UnleashedMail. Activates when
  working with OAuth tokens, stored credentials, encryption keys, or any
  Security.framework / Keychain Services code.
allowed-tools: Read, Grep, Glob
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
│     + deliberately NON-namespaced "userEmail" and "legacyMigrated" items (saveToKeychainLegacy /
│       loadFromKeychainLegacy) — startup discovery must find them WITHOUT knowing the account, so do
│       NOT "fix" them to "<email>:userEmail"; they are unrelated to the deprecated ambient
│       saveToKeychain(key:value:) overload (COREDEV-2378)
├── service "com.unleashedmail.microsoft.auth"  — Microsoft, per account:
│     "<email>:accessToken" / ":refreshToken" / ":tokenExpiry" / ":accountId" / ":mailboxEmail"
│     (+ MSAL keeps its own Keychain-backed cache via cacheConfig.keychainSharingGroup)
└── service "com.unleashedmail.database"         — SQLCipher key (SEPARATE concern):
      "encryption_key_v1" (+ "cipher_salt_v1"); encrypts the email DB only, not the tokens
```

The token / DB-key separation above is what matters for credentials, and no single key wraps them —
but these are **not** the only Keychain services the app uses through `KeychainManager`. Others
include `com.unleashedmail.security` (biometric preference — `BiometricAuthManager`), `.config`,
`.ai`, `.giphy`, `.search-history`, `.saved-searches`, `.user-cache`, `.personalized-weights`,
`UnleashedMail.AITelemetry` / `.SyncObservability` / `.Watchdog` / `.PushReArm`, plus the legacy
`com.gmailclient.*` namespace still being drained by `KeychainServiceNameMigration`. Derive the list
with a grep for `keychainService` rather than trusting any enumeration, including this one — and
note that `com.unleashedmail.security` and the `com.gmailclient.*` database/security names are
merge-gate-protected.

## Use `KeychainManager` — never hand-roll Keychain access

Route ALL Keychain access through the shared `KeychainManager` (`KeychainManager.swift` + its
extensions). Do not write your own `SecItem*` wrapper — `KeychainManager` already handles the
subtleties correctly:

- `save(_:service:account:accessible:synchronizable:accessControl:authContext:isProtectionTransition:)` — the trailing four carry defaults; `isProtectionTransition:` is the one you must sometimes set (see "Two save strategies"). Plus `loadString(...)`, `loadData(...)`, `delete(...)`, `exists(...)`, `listAccountKeys(...)`, `listAccountKeysThrowing(...)`.
- **`exists(...)` and `listAccountKeys(...)` are FAIL-OPEN reads by contract** — `exists` catches every error and returns `false`; `listAccountKeys` swallows every non-`errSecSuccess` status into `[]`, so a locked keychain is indistinguishable from "nothing stored". Never branch a delete, a wipe, a rotation or a migration on either. Use the fail-closed sibling `listAccountKeysThrowing(service:)` wherever an empty result would make you skip work — that is exactly why it exists (a locked keychain during the `com.gmailclient.*` → `com.unleashedmail.*` migration must not read as "no legacy items"). Do not make the lenient variants throw.
- `kSecClassGenericPassword` via `SecItemAdd` / `SecItemCopyMatching` / `SecItemDelete` / `SecItemUpdate`. **There are TWO write paths** and which one runs is decided per call — see "Two save strategies" below. Do not assume either.
- Enforces `synchronizable: false` (never syncs to iCloud Keychain) and defaults to `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`.
- Resolves the entitled keychain access group ONCE per process (`cachedAccessGroup`, a `static let` read from the app's own code signature; `nil` when nothing is explicitly entitled) and pins it into every save / load / delete / list query — so **changing `keychain-access-groups` orphans every already-stored item**, which then becomes unreadable and undeletable through `KeychainManager`. Never synthesise a group from Team ID + Bundle ID (see the warning on `getKeychainAccessGroup`). Supports biometric-gated items (`LAContext` / `SecAccessControl`). Retries exactly three statuses — `errSecNotAvailable`, `errSecInteractionNotAllowed`, `errSecAuthFailed` (`isTransientError`) — via `Thread.sleep` on the CALLING thread, `maxRetries = 10` ≈ 6.5 s worst case; `save` is a synchronous `static func`, so never call it on the MainActor.
- Auto-routes to an **in-memory store under XCTest** — `shouldUseInMemoryStore` is `TestEnvironment.isRunningTests && !useRealKeychain`; call `KeychainManager.resetInMemoryStore()` in `tearDown()` and never call `SecItem*` directly in tests. **Know what this costs you:** `save` selects the strategy, records it in `lastSaveStrategy`, writes the bare `[String: Data]` `inMemoryStore` and returns **before** `performRealKeychainSave` — no `SecItem*` call of any kind, and `accessible` / `accessControl` / `authContext` / `isProtectionTransition` have no effect on the stored value. Nothing in the app or test targets ever sets `KeychainManager.useRealKeychain = true`, so **no test executes `saveLegacy` or `savePrimitive`**. What IS covered: strategy selection (`selectSaveStrategy`, `isMergeGateProtected`, `classify`, `strictBool`), `runAddUpdateLoop` with injected `add` / `update` closures, `buildPrimitivePrimaryKeyQuery`, and the flag / kill-switch write paths. `lastSaveStrategy` is written only on this branch, so it is always `nil` in production. A green suite is not evidence that a change to either real write path is correct — say so when you report on one.

```swift
// Low-level shape ONLY — do not write tokens this way; see the rule under this block
try KeychainManager.save(accessToken, service: "com.unleashedmail.auth",
                         account: "\(email):accessToken", synchronizable: false)
let token = try KeychainManager.loadString(service: "com.unleashedmail.auth",
                                           account: "\(email):accessToken")
try KeychainManager.delete(service: "com.unleashedmail.auth",
                           account: "\(email):accessToken")
```

**Token writes go through the service wrappers, never `KeychainManager.save` directly.** Gmail token
I/O lives in `AuthService+Keychain.swift` / `AuthService+TokenExpiry.swift`, Microsoft in
`MicrosoftAuthService+Keychain.swift` (`+AccountManagement` / `+Helpers` hold the sign-in and
sign-out paths). Use `AuthService.saveToKeychain(email:key:value:updateCache:)` /
`MicrosoftAuthService.saveToKeychain(email:key:value:)` — both return `OSStatus` so the caller can
gate. Credential mutations belong inside `tokenState.withAccountLane(email)`: `performSignOut`
establishes its sign-out tombstone _before_ the network revoke precisely so an in-flight refresh
cannot resurrect deleted credentials, and a write outside the lane is outside that guard. The
`accessToken` + `tokenExpiry` pair must route through `AuthService.writeGenerationPairDurably` —
`KeychainGenerationPairChokePointCITests.test_noOffAllowlistGenerationPairWriter_inAuthServiceSources`
statically scans `AuthService*.swift` and fails CI for any new off-allowlist pair-writer.

## Two save strategies — `KeychainManager.save` picks one per call (COREDEV-2514)

`save` does **not** have a single write path. It calls `selectSaveStrategy(...)` and dispatches
through `performRealKeychainSave`. Both live in `KeychainManager+Primitive.swift`.

| strategy                          | how it writes                                                                                                                            | deletes a live item? |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| **`.legacy`** — the **DEFAULT**   | `deleteExistingKeychainItem` **then** `SecItemAdd` — delete-then-add                                                                     | **yes**, by design   |
| `.primitive` — opt-in, flag-gated | bounded add-first / update-on-duplicate loop: `SecItemAdd`, and on `errSecDuplicateItem` a `SecItemUpdate` against the exact primary key | **no**               |

**`.legacy` is destructive by construction — these are known, accepted properties, not bugs to fix.**
`saveLegacy` passes ONE closure to `retryKeychainOperation`, and that closure contains BOTH the
delete and the add, so the delete re-runs on every one of the 11 attempts. `deleteExistingKeychainItem`
returns `Void` — the `SecItemDelete` `OSStatus` is discarded on purpose (a missing item is the normal
case). There is no read-back and no rollback: if `SecItemAdd` fails after a successful delete, the
credential is **gone**. And if the delete silently fails (locked keychain, access-group mismatch) the
add returns `errSecDuplicateItem`, which `isTransientError` does not classify as transient, so the
save throws on the first attempt with no retry. Closing that loss window is the entire point of
`.primitive` — it is being fixed by the staged rollout, not by patching `.legacy`. Ask before
hardening `saveLegacy` in place.

**The default is `.legacy`.** The rollout flags default false, so with nothing set every write takes
the pre-existing delete-then-add path — except under XCTest, where `save` reaches neither real path
(see the in-memory-store bullet above). `.primitive` activates **only** when _every_ clause holds:

```text
NOT merge-gate-protected                    // isMergeGateProtected — OR-joined over
                                            //   SERVICES: com.unleashedmail/com.gmailclient × .database/.security
                                            //   ACCOUNTS: encryption_key_v1, cipher_salt_v1 + both _backup twins
                                            // The SERVICE arm is load-bearing: it is the only thing covering
                                            // the dynamic cipher_salt_v2_swap_<token> accounts that no static
                                            // account list can enumerate.
  ∧ classify(service:account:) == .rotationHot
                                            // service ∈ {com.unleashedmail.auth, com.unleashedmail.microsoft.auth}
                                            // AND the substring after the account's LAST ':' ∈ {accessToken, tokenExpiry}.
                                            // refreshToken, accountId, userEmail, mailboxEmail, any account with
                                            // no ':', and every legacy com.gmailclient.* name ⟹ .biometricEligible ⟹ .legacy
  ∧ accessControl == nil                    // an ACL install ⟹ .legacy (automatic; no caller action needed)
  ∧ isProtectionTransition == false         // an ACL removal ⟹ .legacy (CALLER-SUPPLIED — see the rule below)
  ∧ killswitch_keychain_primitive inactive  // absent/false = inactive = PERMITS; true/malformed = active ⟹ .legacy
  ∧ pipeline.feature.keychainPrimitive{Gmail,Microsoft}Enabled == true
                                            // providerEnabled picks the key by service == "com.unleashedmail.microsoft.auth";
                                            // the Gmail key is the FALLBACK for every OTHER service, not a Gmail-only key
```

**`isProtectionTransition:` is YOUR argument, and it defaults to the unsafe value.** The real
signature is
`KeychainManager.save(_:service:account:accessible:synchronizable:accessControl:authContext:isProtectionTransition:)`,
and `isProtectionTransition` defaults to `false` — the primitive-permitting value. **Any write whose
purpose is to REMOVE a `kSecAttrAccessControl` (biometric → standard) MUST pass
`isProtectionTransition: true`.** `savePrimitive` writes via `SecItemUpdate`, which cannot remove a
pre-existing ACL, so without the flag the write can take the primitive, report success, and leave
user-presence protection installed after the user turned it off. Exactly two helpers pass it today —
`AuthService.saveStandardToken` and `MicrosoftAuthService.saveAccountTokensAsStandard`; copy them,
and add any third to `MicrosoftBiometricRollbackPrimitiveTests`. The ACL _install_ side needs no
flag: a non-nil `accessControl` auto-routes to `.legacy`.

Despite the type name, `KeychainProtectionClass` selects no protection class and applies no biometry
— `.rotationHot` / `.biometricEligible` are primitive-eligibility labels only. `refreshToken`'s
exclusion from `rotationHotSuffixes` is deliberate and default-safe; do not add it.

Both gates read through the strict `CFBoolean` decoder `KeychainProtectionPolicy.strictBool` — never
`UserDefaults.bool(forKey:)`, which coerces `1` / `"YES"` / `"true"` and would fail OPEN. Both fail
closed toward `.legacy`, but with **opposite polarity**:

- **Enable flags** (`providerEnabled`): only a genuine `CFBoolean true` permits. `false`, absent and
  malformed all give `.legacy`.
- **Kill switch** (`killSwitchInactive`): `true` **or malformed** ⟹ active ⟹ `.legacy`; `false` and
  **absent** ⟹ inactive, which _permits_ the primitive. Absent is the normal shipped state.

So `killSwitchInactive` returning `true` for `.isFalse` / `.absent` is correct, not inverted — do not
"fix" those arms. Writing `false` to `killswitch_keychain_primitive` disables nothing; to force
legacy, set it to a genuine boolean `true` (or leave the enable flags off). Net effect: a corrupt
store can only ever disable the primitive, never enable it.

The kill switch is read DIRECTLY from `UserDefaults` by `selectSaveStrategy` and has **no**
`PipelineFeatureFlags` property by design, so `FeatureFlagService.captureValues` / `restoreValues` /
`applySpecializedKillSwitch` are deliberate no-ops for `.keychainPrimitive` (the
`fts5CorruptionMitigations` precedent). They are not unimplemented — do not wire the switch to
mutate the enable flags.

**Why this matters when you are reading or changing this code.** Two true statements about
`KeychainManager` look contradictory unless you know both paths exist — "it does delete-then-add"
and "it never deletes a live credential" are each correct, about a _different_ strategy. Before
concluding the code is wrong, establish which path you are looking at.

- The primitive re-asserts `kSecAttrAccessible` alongside the data on the update leg
  (`updateAttributes` = `kSecValueData` + `kSecAttrAccessible`), so an existing row is set to
  whatever class _this_ write asks for. **That is a one-way ratchet because of today's callers, not
  because the code enforces it** — `selectSaveStrategy` never inspects `accessible`, and
  `savePrimitive` writes through whatever it was handed. It holds only because every rotation-hot
  writer (`AuthService.saveToKeychain(email:key:value:updateCache:)`,
  `MicrosoftAuthService.saveToKeychain(email:key:value:)`) takes the
  `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` default. A rotation-hot write passing a weaker class
  (`PersonalizedWeightRepository` already passes `…AfterFirstUnlockThisDeviceOnly` elsewhere in the
  app) WOULD apply that weaker class to the existing row. Do not pass a non-default `accessible:` on
  an auth-service `:accessToken` / `:tokenExpiry` write.
- **Open, unverified seam — raise it, do not "fix" it.** Biometric protection is installed on the
  _same_ rotation-hot rows the primitive may write (`AuthService.migrateTokensToBiometric` →
  `saveBiometricTokenSet` → `saveBiometricToken`; `MicrosoftAuthService+BiometricMigration` mirrors
  it). A later ordinary refresh goes through `AuthService.saveToKeychain(email:key:value:updateCache:)`,
  which passes no `accessControl`, no `authContext` and `isProtectionTransition: false` — so with the
  rollout flag on it selects `.primitive`, hits `errSecDuplicateItem` against the ACL-protected row,
  and issues `SecItemUpdate` carrying `kSecAttrAccessible` and no `kSecUseAuthenticationContext`.
  The two strategies differ in OUTCOME here (legacy would delete the ACL row and re-add it
  unprotected, stripping biometry on every refresh; the primitive preserves the ACL), and nothing
  settles which is intended: the in-file comment argues only about the protection class, and no test
  reaches it — `MicrosoftBiometricRollbackPrimitiveTests` asserts strategy SELECTION only and nothing
  in the repo sets `KeychainManager.useRealKeychain = true`. This is part of why the Microsoft flag
  is still off.
- The inner add/update loop is bounded at `primitiveMaxAttempts = 5` TOCTOU cycles (retried
  immediately, no sleep) and then **throws** `KeychainPrimitiveError.writeExhausted` — never a silent
  success. It is a **different top-level error type**, deliberately not a `KeychainManager.KeychainError`
  case and never carrying an `OSStatus`, so `catch let e as KeychainManager.KeychainError` will NOT
  match it. It is thrown straight out of `savePrimitive`; the outer transient ladder does not retry
  it. Map it the way `AuthService.keychainSaveOSStatus(from:)` does — its `default:` arm returns
  `errSecIO`, so the generation-pair writers see a non-success status and fail closed. The outer
  ladder's own exhaustion throws `KeychainError.operationFailed(status)` instead.
- **Do not "unify" the two paths, flip the default, or delete the legacy path** as a cleanup. The
  staged rollout is the security work of COREDEV-2514, and `.legacy` remains the shipped default
  until it completes. Changing which strategy runs is a behaviour change to credential storage —
  ask first.
- **Three constructs look like defects and are load-bearing — do not clean them up.** (a) The
  unreachable trailing `throw KeychainError.operationFailed(errSecInternalError)` at the end of
  `savePrimitive` is a deliberate fail-closed backstop: the function returns `Void`, so deleting it
  would let a future edit that breaks the loop-always-exits invariant fall through to an implicit
  success — a silent-success fail-OPEN. (b) `KeychainPrimitiveError.writeExhausted` is a separate,
  non-`OSStatus` error type on purpose; do not fold it into `KeychainError`. (c)
  `deleteExistingKeychainItem` discards `SecItemDelete`'s status by design.
- **`buildPrimitivePrimaryKeyQuery` intentionally omits `kSecAttrSynchronizable`** — it is exactly
  `kSecClass` + `kSecAttrService` + `kSecAttrAccount` (+ access group), the generic-password
  uniqueness constraint and nothing more. It is the only query in the file that does not pin that
  attribute, and `test_buildPrimitivePrimaryKeyQuery_isExactlyPrimaryKey` asserts the absence. Do
  not "restore consistency" here.
- **The merge gate is deliberate defence-in-depth and is redundant TODAY** — every service and
  account it lists already classifies as `.biometricEligible`, so it changes no current outcome. Do
  not delete it as dead code and do not prune the legacy `com.gmailclient.*` names: the service arm
  is the only thing that would keep the SQLCipher key, the dynamic `cipher_salt_v2_swap_*` backups
  and the `com.unleashedmail.security` items off the primitive if a service is ever added to
  `rotationHotServices`.

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
2. **`synchronizable: false` is ENFORCED; the protection class is a DEFAULT, not an enforcement.** `save` throws `KeychainError.operationFailed(errSecParam)` on `synchronizable: true` before strategy selection and before any `SecItem*` call, and `buildSaveAttributes` hard-codes `kSecAttrSynchronizable: false` — tokens never reach iCloud Keychain. `accessible:` merely _defaults_ to `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`; callers may pass another class (`PersonalizedWeightRepository` passes `…AfterFirstUnlockThisDeviceOnly`), so pass it explicitly for credentials. When you supply an `accessControl:`, `buildSaveAttributes` sets `kSecAttrAccessControl` and **omits `kSecAttrAccessible` entirely** — the `SecAccessControl` carries the class, and `KeychainManager.createAccessControl`'s own default is the weaker `kSecAttrAccessibleWhenUnlocked`, so pass ThisDeviceOnly explicitly as `BiometricAuthManager.createBiometricAccessControl` does. Do not "restore" `kSecAttrAccessible` on the ACL branch. **The `## Accessibility Levels` header at the top of `KeychainManager.swift` is STALE** — it lists `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` as "(Default)"; the parameter default is authoritative. If you reconcile them, fix the comment, never the parameter default.
3. **Wipe on sign-out by an explicit key list, never by a scan.** Follow `AuthService.performSignOut` (deletes `accessToken`, `refreshToken`, `userEmail`, `tokenExpiry`) and `MicrosoftAuthService.signOut(email:)` (those plus `accountId` and `mailboxEmail`). A `listAccountKeys`-driven prefix sweep is fail-open: on a locked keychain it enumerates `[]`, deletes nothing, and reports success. Note the auth services also hold **non-namespaced** legacy accounts — `userEmail` and `legacyMigrated`, written by `saveToKeychainLegacy` — which no `<email>:…` prefix sweep will match.
4. **Token-refresh atomicity is the CALLER's job — `KeychainManager` has no transaction.** `save` writes one item at a time, and the default `.legacy` path deletes before it adds, so a failed write leaves that item _absent_, not unchanged. Persist a generation pair through the existing choke point `AuthService.writeGenerationPairDurably`, which skips the refresh write when the server did not rotate it and writes the new expiry ONLY IF the access write returned `errSecSuccess` (statuses come from `saveToKeychain(email:key:value:updateCache:)`), and roll partial writes back the way `AuthService+CodeExchange.revertTouchedDurableKey` does. Do not add transactional behaviour to `KeychainManager`, and never assume a failed `save` left the old value in place.
5. **Never store tokens in UserDefaults, plist files, a credential file, or unencrypted/SQLCipher GRDB columns** — tokens live only as individual Keychain items.
6. **Don't hand-roll Keychain code or a master-key credential store** — use `KeychainManager`; the SQLCipher key (`EncryptionKeyManager`) is a separate concern.
