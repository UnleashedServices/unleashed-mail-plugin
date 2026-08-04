---
name: grdb-patterns
description: >
  GRDB.swift database patterns for UnleashedMail. Activates when working with
  database models, migrations, queries, or any SQLite/GRDB-related code.
  Covers Record types, migrations, associations, and observation.
allowed-tools: Read, Write, Edit, Grep, Glob
---

# GRDB.swift Patterns — UnleashedMail

> **Naming convention (non-negotiable):** Swift properties are **camelCase**; SQL columns are
> **snake_case**. Map them with an explicit `CodingKeys` enum on every model — never rely on
> "column names match property names." Reference columns in queries by the snake_case name
> (or type-safely via `Column(CodingKeys.foo)`, which resolves to the mapped snake_case name).

## Model Definitions

All database models use GRDB's Record protocols. Define models as structs:

```swift
import GRDB

struct Email: Codable, FetchableRecord, MutablePersistableRecord, Identifiable, Sendable {
    // Swift properties: camelCase
    var id: Int64?
    var accountEmail: String
    var gmailId: String?
    var graphMessageId: String?
    var threadId: String
    var subject: String
    var sender: String
    var snippet: String
    var receivedAt: Date
    var isRead: Bool
    var isStarred: Bool
    var labelIds: [String] // stored as JSON

    static let databaseTableName = "email"

    // SQL columns: snake_case. Explicit mapping — the camelCase property <-> snake_case column
    // bridge lives here, so queries, migrations, and CodingKeys can't drift apart.
    enum CodingKeys: String, CodingKey {
        case id
        case accountEmail = "account_email"
        case gmailId = "gmail_id"
        case graphMessageId = "graph_message_id"
        case threadId = "thread_id"
        case subject
        case sender
        case snippet
        case receivedAt = "received_at"
        case isRead = "is_read"
        case isStarred = "is_starred"
        case labelIds = "label_ids"
    }

    mutating func didInsert(_ inserted: InsertionSuccess) {
        id = inserted.rowID
    }
}
```

### Rules for Models

1. Always implement `Identifiable` with `id: Int64?` for autoincrement primary keys.
2. Every model must include an `accountEmail: String` property (SQL column `account_email`) for account scoping — queries without it risk cross-account data leaks.
3. **Declare an explicit `CodingKeys` enum mapping each camelCase Swift property to its snake_case SQL column.** Do NOT rely on automatic name matching — GRDB would then create/expect camelCase columns, breaking the project's snake_case convention.
4. Complex types (arrays, nested objects) stored as JSON columns with custom `Codable` conformance.
5. Set `databaseTableName` explicitly — do not rely on automatic naming.
6. Provider-specific IDs (e.g., `gmailId` / `gmail_id`, `graphMessageId` / `graph_message_id`) should be nullable since a record belongs to only one provider.

## Migrations

Use `DatabaseMigrator` with versioned, **never-modified** migrations. Column names here are the
**snake_case SQL** identifiers (they must match the `CodingKeys` raw values above):

```swift
var migrator = DatabaseMigrator()

migrator.registerMigration("v1_createEmails") { db in
    try db.create(table: "email") { t in
        t.autoIncrementedPrimaryKey("id")
        t.column("account_email", .text).notNull()
        t.column("gmail_id", .text)
        t.column("graph_message_id", .text)
        t.column("thread_id", .text).notNull().indexed()
        t.column("subject", .text).notNull()
        t.column("sender", .text).notNull()
        t.column("snippet", .text).notNull().defaults(to: "")
        t.column("received_at", .datetime).notNull()
        t.column("is_read", .boolean).notNull().defaults(to: false)
        t.column("is_starred", .boolean).notNull().defaults(to: false)
        t.column("label_ids", .text).notNull().defaults(to: "[]")
    }
    // Composite index for account-scoped queries ordered by date
    try db.create(
        index: "idx_email_account_email_received_at",
        on: "email",
        columns: ["account_email", "received_at"]
    )
}

migrator.registerMigration("v2_addAttachmentsTable") { db in
    try db.create(table: "attachment") { t in
        t.autoIncrementedPrimaryKey("id")
        t.belongsTo("email", onDelete: .cascade, column: "email_id").notNull()  // explicit snake_case FK (belongsTo defaults to camelCase `emailId`)
        t.column("filename", .text).notNull()
        t.column("mime_type", .text).notNull()
        t.column("size", .integer).notNull()
    }
}
```

### Migration Rules

1. **NEVER modify an existing migration.** Always add a new one.
2. Name migrations with a version prefix: `v1_`, `v2_`, etc.
3. Always specify `.notNull()` and `.defaults(to:)` where appropriate.
4. Foreign keys use `.belongsTo()` with explicit `onDelete` behavior **and an explicit `column:`** —
   `belongsTo` defaults to a camelCase FK column (e.g. `emailId`), so pass `column: "email_id"` to keep
   the SQL identifier snake_case (in sync with the model's `CodingKeys` raw values).
5. Column names in `t.column(...)`/indexes are the **snake_case** SQL identifiers — keep them in sync with the model's `CodingKeys` raw values.

## Query Patterns

### Simple fetches

Reference columns by their **snake_case** SQL name (or type-safely via `Column(CodingKeys.foo)`,
which resolves to the same snake_case name — preferred, since it can't drift from the model):

```swift
// Fetch all unread emails for an account, newest first
let unread = try dbQueue.read { db in
    try Email
        .filter(Column("account_email") == accountEmail)   // or Column(Email.CodingKeys.accountEmail)
        .filter(Column("is_read") == false)
        .order(Column("received_at").desc)
        .fetchAll(db)
}
```

> **Mandatory**: Every query MUST filter by account (`account_email` column / `accountEmail` property) to prevent cross-account data leaks.

### Request types for observation

```swift
extension Email {
    static func inboxRequest(accountEmail: String) -> QueryInterfaceRequest<Email> {
        Email
            .filter(Column(CodingKeys.accountEmail) == accountEmail)   // resolves to "account_email"
            .filter(sql: "label_ids LIKE '%\"INBOX\"%'")
            .order(Column(CodingKeys.receivedAt).desc)
    }
}
```

## Database Observation (ValueObservation)

For live UI updates, use `ValueObservation`. Prefer the modern GRDB 7+ async `for try await` pattern:

```swift
// In ViewModel — modern GRDB 7+ async observation (preferred)
func startObserving(accountEmail: String) async {
    let observation = ValueObservation.tracking { db in
        try Email.inboxRequest(accountEmail: accountEmail).fetchAll(db)
    }
    do {
        for try await emails in observation.values(in: dbQueue) {
            self.messages = emails
        }
    } catch {
        Logger.debug("Observation failed: \(error)", category: .database)
    }
}
```

Callback-based alternative (legacy, use only when async context is unavailable):

```swift
let observation = ValueObservation.tracking { db in
    try Email.inboxRequest(accountEmail: accountEmail).fetchAll(db)
}

let cancellable = observation.start(in: dbQueue, onError: { error in
    // handle
}, onChange: { [weak self] emails in
    self?.messages = emails
})
```

### Observation Rules

1. **Prefer the async `for try await` pattern** (GRDB 7+) — it integrates naturally with Swift concurrency and structured task cancellation.
2. Use `ValueObservation` for read-only UI bindings — not manual polling.
3. When using the callback-based API, store the cancellable and cancel it on deinit.
4. For write-heavy paths, use `.removeDuplicates()` to avoid excessive UI updates.

## DatabaseQueue vs DatabasePool — UnleashedMail's split

**Production: `DatabasePool`.** UnleashedMail's prod database is a `DatabasePool` (`DatabaseService.useDatabasePool = true`). DatabasePool manages one writer SQLite connection plus a pool of readers; WAL mode is enabled. **All write operations are FIFO-serialized through a single writer dispatch queue** — only one thread writes at a time. A single `try await dbPool.write { db in ... }` block is fully atomic; read-modify-write inside that block is a safe primitive and should be the default tool when ordering matters.

**Tests: `DatabaseQueue`.** Tests use in-memory `DatabaseQueue` (`useDatabasePool = false`) because SQLCipher's reduced `kdf_iter` (set for test speed) is incompatible with the WAL reopen DatabasePool requires. This is a test-only constraint, not a design preference — do not extrapolate it to "we should switch prod to DatabaseQueue."

**Choosing a primitive when ordering matters:** Prefer GRDB's atomic write block over a Swift-level serialization actor when the ordering invariant can be expressed as "later writes must observe a larger monotonic key than already-committed writes." Encode the invariant in a column, check it inside the `dbPool.write` block, and let GRDB's writer queue enforce the FIFO at the database boundary. Reach for a Swift-level serializer actor only when the invariant cannot be expressed in SQL or spans multiple uncoordinated tables.

## Testing

Always test database code with an in-memory `DatabaseQueue`. This matches production's test-environment fallback because SQLCipher's reduced `kdf_iter` cannot reopen as WAL — not because `DatabaseQueue` is the production default.

```swift
func makeTestDB() throws -> DatabaseQueue {
    let db = try DatabaseQueue()
    var migrator = AppDatabase.migrator // reuse production migrations
    try migrator.migrate(db)
    return db
}
```
