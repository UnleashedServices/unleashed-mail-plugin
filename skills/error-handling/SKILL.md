---
name: error-handling
description: >
  Error handling and logging patterns for UnleashedMail. Covers typed Swift errors,
  PII redaction, structured logging, recovery patterns, and testing error paths.
  Activates when implementing error handling, logging, or error recovery logic.
allowed-tools: Read, Grep, Glob
---

# Error Handling and Logging Patterns — UnleashedMail

## Overview

UnleashedMail uses typed Swift errors with `do-catch` + `Logger` for all error handling.
No `try?` silently swallowing errors. All errors are logged with `PIIRedactor` for
email addresses, subjects, and content.

## Error Types

Providers throw the app's **real** typed errors — do NOT invent your own. The canonical
provider-agnostic error is **`EmailServiceError`** (`Services/EmailServiceProtocol.swift`): both
`GmailService` and `MicrosoftGraphService` conform to `EmailServiceProtocol`, and
`AccountScopedServiceProvider.activeService()` returns `any EmailServiceProtocol`, so a
provider-agnostic caller catches `EmailServiceError`:

```swift
// The app's real type — REFERENCE it, don't redefine it. Exact cases/signatures:
internal enum EmailServiceError: LocalizedError, Sendable {
    case notAuthenticated
    case invalidResponse
    case requestFailed(statusCode: Int)
    case rateLimited                         // NO associated value
    case notFound
    case folderNotFound(folderName: String)
    case networkError(Error)                 // UNLABELED associated value — .networkError(err)
    case decodingError(Error)                // UNLABELED
    case operationNotSupported
    // helpers: errorDescription, isAuthenticationError, isRateLimited
}
```

Provider-/domain-specific errors also exist — catch these where you touch that layer directly:

- `GmailError` (`GmailService+APIModels.swift`) — Gmail internals; may surface from the Gmail path even through `EmailServiceProtocol`.
- `MicrosoftAuthError` (`MicrosoftAuthService+Errors.swift`) — Microsoft auth.
- `AuthError` (`AuthService.swift`) — Google OAuth.
- Unsupported-provider-operation: `EmailServiceError.operationNotSupported` **or** `ProviderParityError` (`AccountScopedServiceProvider.swift`).

Match their real conformances (`LocalizedError, Sendable`) and case signatures — e.g. `.networkError(error)` (unlabeled, not `.networkError(underlying:)`/`.networkError(description:)`), `.requestFailed(statusCode:)`, `.rateLimited` (no payload). Prefer the helpers `isAuthenticationError` / `isRateLimited` over pattern-matching invented cases. (`Email` below is an illustrative row model — use the app's real email model type in real code.)

## Error Handling Patterns

### Service Layer

```swift
func fetchMessage(id: String) async throws -> Email {
    do {
        let token = try await tokenManager.validAccessToken()
        let response = try await api.getMessage(id: id, token: token)
        return try response.toEmail()
    } catch let error as EmailServiceError {
        Logger.debug("Email service error fetching \(id): \(error)", category: .network)
        throw error
    } catch {
        Logger.debug("Unexpected error fetching \(id): \(error)", category: .network)
        throw EmailServiceError.networkError(error)   // unlabeled associated value
    }
}
```

### ViewModel Layer

```swift
@Observable @MainActor
final class InboxViewModel {
    var state: ViewState<[Email]> = .idle
    var error: EmailServiceError?

    func fetchMessages() async {
        state = .loading
        do {
            let messages = try await emailService.fetchInbox()
            state = .loaded(messages)
            error = nil
        } catch let error as EmailServiceError {
            state = .idle
            self.error = error
            Logger.debug("Failed to fetch inbox: \(error.localizedDescription)", category: .ui)
        } catch {
            state = .idle
            self.error = EmailServiceError.networkError(error)
            Logger.debug("Unexpected error fetching inbox: \(error)", category: .ui)
        }
    }
}
```

### View Layer

```swift
struct InboxView: View {
    @State private var viewModel: InboxViewModel

    var body: some View {
        Group {
            switch viewModel.state {
            case .idle:
                EmptyStateView()
            case .loading:
                LoadingView()
            case .loaded(let messages):
                MessageListView(messages: messages)
            }
        }
        .alert("Error", isPresented: Binding(
            get: { viewModel.error != nil },
            set: { if !$0 { viewModel.error = nil } }
        ), presenting: viewModel.error) { _ in
            Button("OK") { viewModel.error = nil }
        } message: { error in
            Text(error.localizedDescription)   // EmailServiceError conforms to LocalizedError
        }
    }
}
```

## Logging Patterns

### Logger Categories

```swift
extension Logger {
    static let network = Logger(subsystem: "com.unleashedservices.unleashedmail", category: "network")
    static let auth = Logger(subsystem: "com.unleashedservices.unleashedmail", category: "auth")
    static let ui = Logger(subsystem: "com.unleashedservices.unleashedmail", category: "ui")
    static let database = Logger(subsystem: "com.unleashedservices.unleashedmail", category: "database")
    static let storeKit = Logger(subsystem: "com.unleashedservices.unleashedmail", category: "storeKit")
    static let ai = Logger(subsystem: "com.unleashedservices.unleashedmail", category: "ai")
    static let general = Logger(subsystem: "com.unleashedservices.unleashedmail", category: "general")
}
```

### PII Redaction

Never log sensitive data directly:

```swift
// ❌ Bad — logs PII
Logger.debug("Sending email to \(recipient) with subject '\(subject)'", category: .network)

// ✅ Good — redacts PII
Logger.debug("Sending email to \(PIIRedactor.redactEmail(recipient)) with subject '\(PIIRedactor.redactSubject(subject))'", category: .network)
```

### PIIRedactor Implementation

```swift
struct PIIRedactor {
    static func redactEmail(_ email: String) -> String {
        let components = email.split(separator: "@")
        guard components.count == 2 else { return "[REDACTED]" }
        let local = String(components[0])
        let domain = String(components[1])
        let redactedLocal = String(local.prefix(2)) + String(repeating: "*", count: max(0, local.count - 2))
        return "\(redactedLocal)@\(domain)"
    }

    static func redactSubject(_ subject: String) -> String {
        guard subject.count > 10 else { return "[REDACTED]" }
        return String(subject.prefix(10)) + "..."
    }

    static func redactContent(_ content: String) -> String {
        guard content.count > 50 else { return "[REDACTED]" }
        return String(content.prefix(50)) + "..."
    }
}
```

## Recovery Patterns

### Retry Logic

```swift
func withRetry<T: Sendable>(
    maxAttempts: Int = 3,
    operation: @Sendable () async throws -> T
) async throws -> T {
    for attempt in 1...maxAttempts {
        do {
            return try await operation()
        } catch {
            if attempt == maxAttempts {
                throw error
            }
            Logger.debug("Operation failed (attempt \(attempt)), retrying: \(error)", category: .network)
            try await Task.sleep(for: .seconds(pow(2.0, Double(attempt - 1))))
        }
    }
    fatalError("Unreachable")
}
```

### Graceful Degradation

```swift
func loadMessages(accountEmail: String) async {
    do {
        // Try to load from API
        let messages = try await api.fetchMessages()
        self.messages = messages
    } catch EmailServiceError.networkError {
        // Fall back to cached messages
        Logger.debug("Network unavailable, using cached messages", category: .network)
        do {
            self.messages = try await dbQueue.read { db in
                // Scope EVERY query by account_email — never fetch across accounts (CLAUDE.md invariant).
                try Email
                    .filter(Column("account_email") == accountEmail)
                    .fetchAll(db)
            }
        } catch {
            Logger.debug("Cache fallback also failed: \(error)", category: .database)
            self.error = EmailServiceError.networkError(error)
        }
    } catch {
        // Other failures — keep the typed error if it is one, else wrap
        self.error = (error as? EmailServiceError) ?? .networkError(error)
    }
}
```

## Testing Error Paths

```swift
func test_fetchMessages_handlesNetworkError() async throws {
    // Arrange
    mockService.shouldThrow = EmailServiceError.networkError(URLError(.notConnectedToInternet))

    // Act
    await sut.fetchMessages()

    // Assert
    XCTAssertEqual(sut.state, .idle)
    // EmailServiceError isn't Equatable (its .networkError wraps a non-Equatable Error),
    // so match the case rather than XCTAssertEqual on the whole value.
    guard case .networkError = sut.error else {
        return XCTFail("expected .networkError, got \(String(describing: sut.error))")
    }
}
```
