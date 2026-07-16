---
name: provider-parity
description: >
  Mail provider parity enforcement for UnleashedMail. Activates automatically when
  working on Gmail-specific or Microsoft Graph-specific code, EmailServiceProtocol
  implementations, sync services, or any code touching email fetching, sending,
  folder/label management, attachments, or push notification handling.
  Ensures both providers stay feature-aligned.
allowed-tools: Read, Grep, Glob
---

# Provider Parity — Gmail ↔ Microsoft Graph

## Why This Exists

UnleashedMail supports two mail backends behind one shared protocol. Every time you add,
modify, or remove a capability in one provider, the other must be updated to match — or
the gap must be **declared** in the provider's `ServiceCapabilities` and, if a call site
can still be reached, guarded with `ProviderParityError`. This skill fires automatically
to prevent silent parity drift.

## The Shared Abstraction — `EmailServiceProtocol`

All provider-specific code lives behind **`EmailServiceProtocol`**
(`Unleashed Mail/Sources/Services/EmailServiceProtocol.swift`). Both `GmailService` and
`MicrosoftGraphService` conform. ViewModels and UI code **never** reference those concrete
types — they hold `any EmailServiceProtocol`, resolved through `AccountScopedServiceProvider`.

```swift
internal protocol EmailServiceProtocol: AnyObject, Sendable {
    var accountEmail: String? { get }
    var accountType: AccountType { get }            // .google | .microsoft
    var capabilities: ServiceCapabilities { get }   // declarative parity — see below

    func getCurrentUser() async throws -> User

    // Messages — batch-oriented; both providers normalize to the shared `Email` model.
    func fetchMessages(folderId: String, maxResults: Int, paginationToken: PaginationToken?)
        async throws -> (emails: [Email], nextToken: PaginationToken)
    func fetchMessage(id: String, forceRefresh: Bool) async throws -> Email
    func batchFetchMessages(ids: [String], onEmailFetched: ((Email) async -> Void)?)
        async throws -> [String: Email]
    func searchMessages(query: String, maxResults: Int) async throws -> [Email]

    // State changes — batch by ids (singular convenience overloads are default-implemented).
    func markAsRead(ids: [String]) async throws
    func markAsUnread(ids: [String]) async throws
    func starMessages(ids: [String]) async throws
    func unstarMessages(ids: [String]) async throws
    func moveToTrash(ids: [String]) async throws
    func deleteMessages(ids: [String]) async throws
    func archiveMessages(ids: [String]) async throws
    func reportAsSpam(ids: [String]) async throws
    func moveToFolder(ids: [String], folderId: String) async throws

    // Folders (Gmail labels are modeled as `Folder` too).
    func fetchFolders(forceRefresh: Bool) async throws -> [Folder]
    func createFolder(name: String, parentId: String?) async throws -> Folder
    func deleteFolder(id: String) async throws

    // Send / drafts. NOTE the `authAccount:` overload is a REAL protocol requirement —
    // it pins the send to the composing account so a mid-drain account switch can't send
    // from B while draining A's outbox.
    func sendMessage(draft: EmailDraft, attachmentCache: [String: Data]?, authAccount: String?) async throws
    func createDraft(draft: EmailDraft, attachmentCache: [String: Data]?) async throws -> String
    func updateDraft(draftId: String, draft: EmailDraft, attachmentCache: [String: Data]?) async throws
    func deleteDraft(draftId: String) async throws
    func listDrafts() async throws -> [Email]

    // Attachments are fetched as raw bytes; the provider owns MIME/JSON decoding. NOTE the
    // `onProgress:` parameter is part of the PROTOCOL REQUIREMENT (a large attachment reports
    // 0.0→1.0 as it downloads). The two-argument `(messageId:attachmentId:)` form is only a
    // convenience EXTENSION that calls this with `onProgress: nil` — do NOT snapshot the convenience
    // form as the requirement (full review; verified against EmailServiceProtocol.swift:231).
    func fetchAttachmentData(
        messageId: String,
        attachmentId: String,
        onProgress: (@Sendable (Double) -> Void)?
    ) async throws -> Data
}
```

`PaginationToken` (`Models/PaginationToken.swift`) is a provider-agnostic enum — Gmail's
`nextPageToken` and Graph's `@odata.nextLink` both normalize into it, so ViewModels never
see a raw token string.

## Service Resolution — never touch a concrete service

Resolve the active provider through `AccountScopedServiceProvider` (see the app's
`CLAUDE.md` "Service Resolution"). This is the same containment boundary that keeps one
account's data from leaking into another.

```swift
// Provider-agnostic call — the ONLY pattern ViewModels/services use:
let service = try serviceProvider.activeService()          // -> any EmailServiceProtocol
let (emails, next) = try await service.fetchMessages(folderId: "INBOX", maxResults: 50, paginationToken: nil)

// Provider-specific escape hatch (throws if the active account is the wrong provider):
let gmail = try serviceProvider.gmailServiceGuarded()

// Guard a provider-specific operation at the top of the method:
try serviceProvider.validateSupported(.scheduledSend)      // throws ProviderParityError if unsupported
```

## Declaring parity differences — `ServiceCapabilities`

Genuine feature differences are **declared**, not discovered at a crash site. Each provider
exposes a static `ServiceCapabilities` value; UI gates on the flag rather than hard-coding a
provider check.

```swift
internal struct ServiceCapabilities: Sendable, Equatable {
    let supportsMultipleLabels: Bool
    let supportsScheduledSend: Bool
    let supportsArchive: Bool
    let supportsUndoSend: Bool
    let supportsCategories: Bool
    let supportsImportance: Bool
    let supportsReadReceipts: Bool
    static let gmail = Self(/* … */)
    static let microsoft = Self(/* … */)
}
```

Current declared differences (keep this in sync with the source of truth in
`EmailServiceProtocol.swift`):

| Capability | Gmail (`.google`) | Microsoft (`.microsoft`) |
|---|---|---|
| `supportsMultipleLabels` | ✅ | ❌ (single parent folder) |
| `supportsScheduledSend` | ✅ | ❌ (needs Graph `deferredDeliveryTime`) |
| `supportsArchive` | ✅ | ✅ (may be false for consumer accounts) |
| `supportsUndoSend` | ✅ | ❌ |
| `supportsCategories` | ❌ | ✅ |
| `supportsImportance` | ❌ | ✅ |
| `supportsReadReceipts` | ❌ | ✅ |

```swift
// Gate UI on a capability — NOT on `accountType == .google`:
if service.capabilities.supportsScheduledSend {
    ScheduleSendButton()
}
```

## Parity Mapping Reference (API endpoints)

Use this when implementing a feature to find the counterpart call:

| Capability | Gmail Implementation | Graph Implementation |
|---|---|---|
| **Auth** | Manual OAuth 2.0 + custom `TokenManager` actor | MSAL `MSALPublicClientApplication` + silent/interactive |
| **Fetch inbox** | `GET /messages?labelIds=INBOX` | `GET /me/mailFolders/inbox/messages` |
| **Get message** | `GET /messages/{id}?format=full` → MIME decode | `GET /me/messages/{id}` → JSON with HTML body |
| **Send** | `POST /messages/send` with base64url RFC 2822 | `POST /me/sendMail` with JSON envelope |
| **Reply** | Build RFC 2822 with `In-Reply-To` + `References` headers | `POST /me/messages/{id}/reply` |
| **Forward** | Build RFC 2822 with forwarded MIME | `POST /me/messages/{id}/forward` |
| **Mark read** | `POST /messages/{id}/modify` remove `UNREAD` label | `PATCH /me/messages/{id}` set `isRead: true` |
| **Star** | `POST /messages/{id}/modify` add `STARRED` label | `PATCH /me/messages/{id}` set `flag.flagStatus: "flagged"` |
| **Archive** | Remove `INBOX` label | `POST /me/messages/{id}/move` to `archive` |
| **Trash** | `POST /messages/{id}/trash` | `POST /me/messages/{id}/move` to `deleteditems` |
| **Move** | `POST /messages/{id}/modify` add/remove labels | `POST /me/messages/{id}/move` to folder ID |
| **Folders** | `GET /labels` (flat, multi-assign) | `GET /me/mailFolders` (hierarchical, single-parent) |
| **Create folder** | `POST /labels` | `POST /me/mailFolders` (or child of parent) |
| **Attachments (small)** | Inline in multipart MIME (<5MB) | Inline in JSON (<3MB) |
| **Attachments (large)** | Multipart upload (<35MB) | Upload session (<150MB) |
| **Push** | Pub/Sub `watch()` → historyId | Webhook subscription → resource ID |
| **Incremental sync** | `GET /history?startHistoryId=` | `GET /me/mailFolders/inbox/messages/delta` |
| **Pagination** | `pageToken` / `nextPageToken` | `@odata.nextLink` |
| **Batch** | Gmail batch API (multipart) | `POST /$batch` (JSON, max 20 requests) |
| **Search** | Gmail search syntax (`from:`, `subject:`, etc.) | `$filter` and `$search` OData parameters |
| **Rate limits** | 250 quota units/sec per user | 10,000 requests / 10 min per mailbox |

## Workflow: Implementing a New Capability

### Step 1 — Protocol first
Add the method to `EmailServiceProtocol` **before** writing either implementation. If it is a
truly optional feature, add a `ProviderOperation` case and a `ServiceCapabilities` flag too.

### Step 2 — Implement the first provider
Pick the provider you know best. Follow TDD (invoke the `swift-tdd` skill).

### Step 3 — Implement (or explicitly gap) the second provider
Use the mapping table to find the equivalent call. If the second provider can't do it:

1. **Emulate** if reasonable (e.g. Gmail has no native snooze → remove from inbox + schedule a re-label).
2. Otherwise **declare it unsupported** — flip the `ServiceCapabilities` flag to `false`, gate the
   UI on that flag, and make any still-reachable call site throw:

```swift
// MicrosoftGraphService — genuinely unsupported operation
func scheduleSend(draft: EmailDraft, at date: Date) async throws {
    throw ProviderParityError.unsupportedForProvider(operation: "scheduledSend", provider: .microsoft)
}
```

`ProviderParityError.unsupportedForProvider(operation:provider:)`
(`Services/AccountScopedServiceProvider.swift`) is the **only** acceptable way to express a
parity gap at a call site. Its `errorDescription` already renders a user-facing
"*… is not yet available for \(provider.displayName) accounts.*" — the UI shows a
`CuratorActionMismatchNotice` rather than a raw error.

### Step 4 — Parity tests against both providers
Regression tests live in `Unleashed MailTests/ProviderParityRegressionTests.swift` and run
against the in-repo stubs `StubGoogleEmailService` / `StubMicrosoftEmailService` (both
conform to `EmailServiceProtocol`). Assert the shared operations work on both and that
provider-specific ones are correctly scoped:

```swift
func test_providerOperation_fetchMessages_supportedByBoth() { /* both stubs succeed */ }
func test_providerOperation_scheduledSend_googleOnly()     { /* google ok; microsoft throws */ }
```

Any type that takes a service must accept **`any EmailServiceProtocol`**, never a concrete
service (see `test_cidImageResolver_acceptsAnyEmailServiceProtocol`).

### Step 5 — Parity audit before commit

```bash
# 1. Both providers still conform (compile check)
xcodebuild build -scheme "Unleashed Mail" -destination 'platform=macOS' 2>&1 \
  | grep "does not conform to protocol" | head -10

# 2. Provider concretes must NOT leak into ViewModels/Views (parity violation → zero results)
grep -rn "GmailService\|MicrosoftGraphService\|MSALResult\|GmailAPI\." --include='*.swift' \
    "Unleashed Mail/Sources/ViewModels/" "Unleashed Mail/Sources/Views/"

# 3. Every ProviderOperation case should be covered by a capability decision or a parity test
grep -rn "ProviderParityError.unsupportedForProvider" --include='*.swift' "Unleashed Mail/Sources/"
```

## The `ProviderOperation` catalogue

`ProviderOperation` (`Services/AccountScopedServiceProvider.swift`) enumerates every gate-able
operation — pass one to `validateSupported(_:)`:

`fetchMessages`, `sendMessage`, `markAsRead`, `markAsUnread`, `star`, `archive`, `trash`,
`delete`, `moveToFolder`, `search`, `fetchAttachments`, `createDraft`, `updateDraft`,
`deleteDraft`, `snooze`, `scheduledSend`, `autoRespond`, `workflowExecution`,
`signatureImport`, `pushNotifications`, `batchModifyLabels`, `modifyLabels`, `emptyTrash`,
`emptySpam`.

## Domain Model Normalization

Both providers normalize to the shared **`Email`** model (`Models/Email.swift`) — never a
provider-native shape:

```swift
struct Email: Identifiable, Sendable {
    let id: String
    let threadId: String            // Gmail threadId; Graph conversationId
    let subject: String
    let from: EmailAddress
    let to: [EmailAddress]
    let cc: [EmailAddress]
    let date: Date
    let snippet: String
    let bodyHTML: String?           // both providers normalize to HTML (sanitized before WKWebView)
    let isRead: Bool
    let isStarred: Bool             // Gmail STARRED label; Graph flag.flagStatus
    let labelIds: [String]          // Gmail labelIds; Graph [parentFolderId]
    let attachments: [EmailAttachment]
    let accountEmail: String?       // account scoping — every row is account-tagged
    // … (see Models/Email.swift for the full shape)
}
```

If a field has different semantics per provider, document the normalization in the mapping
code — not on the model.

## Shared Error Type

Provider-agnostic failures surface as **`EmailServiceError`** (defined in
`EmailServiceProtocol.swift`): `.notAuthenticated`, `.invalidResponse`,
`.requestFailed(statusCode:)`, `.rateLimited`, `.notFound`, `.folderNotFound(folderName:)`,
`.networkError(Error)`. See the `error-handling` skill for the canonical mapping. Parity /
containment failures use `ProviderParityError` (above), which is distinct.

## Hard Rules

1. **Protocol-first, always.** Never add a public method to one service without adding it to `EmailServiceProtocol`.
2. **No provider concretes in ViewModels/Views.** Hold `any EmailServiceProtocol`; resolve via `AccountScopedServiceProvider.activeService()`.
3. **Declare differences in `ServiceCapabilities`; gate UI on the flag** — not on `accountType`.
4. **Every genuine gap throws `ProviderParityError.unsupportedForProvider`** at any reachable call site, and is covered by a parity regression test.
5. **Tests run against both stubs.** A feature isn't done until `StubGoogleEmailService` and `StubMicrosoftEmailService` both pass in `ProviderParityRegressionTests`.
6. **The reviewer will flag it.** `swift-reviewer` treats missing parity as a 🔴 BLOCKER (`parity` category).
