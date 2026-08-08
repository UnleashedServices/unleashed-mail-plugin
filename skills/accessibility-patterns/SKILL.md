---
name: accessibility-patterns
description: >
  Accessibility patterns and compliance for UnleashedMail. Covers VoiceOver support,
  keyboard navigation, Dynamic Type, color contrast, and testing. Activates when
  implementing accessible UI, testing a11y features, or ensuring compliance.
allowed-tools: Read, Grep, Glob
---

# Accessibility Patterns — UnleashedMail

## Overview

UnleashedMail is fully accessible with VoiceOver, keyboard navigation, Dynamic Type,
and color contrast compliance. All UI components follow macOS accessibility guidelines.
Accessibility is mandatory — no feature ships without full a11y support.

## Core Principles

1. **No accessibility without functionality** — Every interactive element must be fully usable by assistive technologies
2. **Keyboard-first design** — All actions available via keyboard shortcuts
3. **Dynamic Type support** — Text scales with system settings
4. **Color independence** — No color-only state indicators
5. **Clear focus management** — Logical tab order, visible focus rings

## SwiftUI Accessibility Modifiers

### Basic Labels and Hints

```swift
Button("Send", systemImage: "paperplane") {
    // action
}
.accessibilityLabel("Send email")
.accessibilityHint("Sends the composed email to recipients")
```

### Custom Controls

```swift
// Custom gesture-based control
Rectangle()
    .fill(Color.curatorPrimary)   // Curator token, not raw Color.blue (see Semantic Colors below)
    .frame(width: 50, height: 50)
    .onTapGesture {
        toggleStar()
    }
    .accessibilityElement(children: .ignore)
    .accessibilityLabel(isStarred ? "Remove star" : "Add star")
    .accessibilityHint("Toggles star status for this message")
    .accessibilityAddTraits(.isButton)
    .accessibilityValue(isStarred ? "Starred" : "Not starred")
```

### Complex Components

```swift
List(messages, selection: $selectedMessage) { message in
    MessageRow(message: message)
}
.accessibilityLabel("Message list")
.accessibilityHint("Select a message to view its contents")
```

### Message Row

```swift
struct MessageRow: View {
    let message: MailMessage

    var body: some View {
        HStack {
            Circle()
                .fill(message.isRead ? Color.clear : Color.curatorSecondary)  // unread dot token
                .frame(width: 8, height: 8)
                .accessibilityHidden(true)  // Decorative

            VStack(alignment: .leading) {
                Text(message.sender)
                    .font(.headline)
                Text(message.subject)
                    .font(.subheadline)
                    .lineLimit(1)
                Text(message.snippet)
                    .font(.caption)
                    .lineLimit(1)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double tap to open message")
        .accessibilityValue(message.isRead ? "Read" : "Unread")
    }

    private var accessibilityLabel: String {
        let readStatus = message.isRead ? "" : "Unread, "
        return "\(readStatus)From \(message.sender), \(message.subject)"
    }
}
```

## Focus Management

### Keyboard Navigation

```swift
@AccessibilityFocusState private var focusedField: Field?

enum Field {
    case to, subject, body
}

TextField("To", text: $to)
    .accessibilityFocused($focusedField, equals: .to)

TextField("Subject", text: $subject)
    .accessibilityFocused($focusedField, equals: .subject)

TextEditor(text: $body)
    .accessibilityFocused($focusedField, equals: .body)
```

### Rotor Support

```swift
// Custom rotor for navigation
.accessibilityRotor("Unread Messages") {
    ForEach(unreadMessages) { message in
        AccessibilityRotorEntry(message.subject, id: message.id)
    }
}
```

## Dynamic Type

### Scalable Text

```swift
// UnleashedMail scales text APP-WIDE via CuratorTheme, not SwiftUI Dynamic Type.
// Use the Curator typography sizes (CGFloat point sizes):
// SCALABLE text uses the Curator scaler — the ONLY form that responds to the user's font-scale
// preference (appState.uiPreferences.uiFontScale). This is the accessible default:
Text("Message")
    .font(CuratorTheme.scaledFont(size: CuratorTheme.Typography.bodySize,
                                  weight: .regular,
                                  scale: appState.uiPreferences.uiFontScale))

// A bare `.system(size: CuratorTheme.Typography.…)` is the BASE point size and is NOT user-scalable —
// it does not change with uiFontScale. Use it only where fixed sizing is intentional (chrome that must
// not reflow); it is NOT the answer for "scalable text".
Text("Welcome to UnleashedMail")
    .font(.system(size: CuratorTheme.Typography.headlineSize, weight: .semibold))  // fixed 18pt base

// ❌ Do NOT use SwiftUI semantic fonts — the design system uses CuratorTheme.Typography
//    (displaySize 44, headlineSize 18, titleSize 16, bodySize 14, bodySmallSize 13,
//    labelSize 11, microSize 10), matching the shipped Curator components.
Text("Message").font(.body)      // ❌
Text("Title").font(.largeTitle)  // ❌
```

### Layout Adaptation

```swift
// Content text must SCALE — use the Curator scaler, not a bare `.system(size:)` (fixed, chrome-only).
VStack {
    Text("Subject")
        .font(CuratorTheme.scaledFont(size: CuratorTheme.Typography.titleSize,
                                      weight: .semibold,
                                      scale: appState.uiPreferences.uiFontScale))
    Text(subject)
        .font(CuratorTheme.scaledFont(size: CuratorTheme.Typography.bodySize,
                                      weight: .regular,
                                      scale: appState.uiPreferences.uiFontScale))
        .lineLimit(nil)  // Allow wrapping
        .fixedSize(horizontal: false, vertical: true)  // Grow vertically
}
```

## Color and Contrast

### Semantic Colors

```swift
// ✅ Curator semantic colors (adapt to light/dark; per CLAUDE.md, never raw Color.*)
Color.curatorOnSurface          // primary text
Color.curatorOnSurfaceVariant   // secondary / metadata text
Color.curatorPrimary            // accent / selection
Color.curatorSecondary          // unread dots / badges
Color.curatorError              // error

// ❌ Raw SwiftUI colors AND bare semantic colors — none are the sanctioned Curator tokens
Color.blue
Color.white
Color.primary
Color.accentColor
```

### State Indicators

```swift
// ✅ Multiple indicators (icon + text — don't convey state by color alone) + Curator colors
HStack {
    Image(systemName: message.isStarred ? "star.fill" : "star")
    Text(message.subject)
}
.foregroundStyle(message.isStarred ? Color.curatorAccent : Color.curatorOnSurfaceVariant)

// ❌ Color only, and raw (.yellow/.primary) instead of Curator tokens
Text(message.subject)
    .foregroundStyle(message.isStarred ? .yellow : .primary)
```

## VoiceOver Announcements

### Live Updates

```swift
// Announce when content changes
.onChange(of: messageCount) { oldValue, newValue in
    let announcement = "\(newValue) messages"
    AccessibilityNotification.Announcement(announcement).post()
}
```

### Custom Announcements

```swift
func sendEmail() async {
    // Send logic...
    AccessibilityNotification.Announcement("Email sent successfully").post()
}
```

## Testing Accessibility

### Xcode Accessibility Inspector

```bash
# Launch Accessibility Inspector
open /Applications/Xcode.app/Contents/Developer/Applications/Accessibility\ Inspector.app
```

### UI Tests

```swift
func testMessageRow_accessibility() throws {
    let app = XCUIApplication()
    app.launch()

    let messageRow = app.descendants(matching: .any)["Message from John Doe"]
    XCTAssertTrue(messageRow.exists)
    XCTAssertEqual(messageRow.label, "From John Doe, Welcome to the team")
    XCTAssertEqual(messageRow.value as? String, "Unread")
}
```

### Manual Testing Checklist

- [ ] VoiceOver can navigate all elements
- [ ] Tab key moves focus logically
- [ ] All buttons have labels and hints
- [ ] Dynamic Type scales text appropriately
- [ ] High Contrast mode works
- [ ] Reduced Motion respects preferences
- [ ] Keyboard shortcuts work without mouse

## Common Patterns

### Form Fields

```swift
TextField("Email Address", text: $email)
    .accessibilityLabel("Recipient email address")
    .accessibilityHint("Enter the email address of the recipient")
    .textContentType(.username)
```

### Progress Indicators

```swift
ProgressView("Sending email...", value: progress)
    .accessibilityLabel("Sending email progress")
    .accessibilityValue("\(Int(progress * 100)) percent complete")
```

### Modal Dialogs

```swift
.sheet(isPresented: $showCompose) {
    ComposeView()
        .accessibilityAddTraits(.isModal)
}
```

## Dual Implementation Accessibility

Since UnleashedMail has dual implementations (native + WebKit compose; docked + floating AI), both must be equally accessible. (Email detail is single-renderer — `SimpleEmailWebView` only — so it has no dual-renderer parity requirement.)

### Compose Editor

```swift
// Native SwiftUI editor
TextEditor(text: $body)
    .accessibilityLabel("Email body")
    .accessibilityHint("Compose the content of your email")

// WebKit editor
WebView(html: composeHTML)
    .accessibilityLabel("Email composition editor")
    .accessibilityHint("Use rich text editing to compose your email")
```

### Email Detail

`SimpleEmailWebView` is the sole production email-body renderer (the legacy second renderer was removed), so there is no dual-renderer parity requirement here — just ensure the single renderer is accessible:

```swift
// SimpleEmailWebView — the sole production email-body renderer
WebView(html: messageHTML)
    .accessibilityLabel("Email content")
    .accessibilityHint("Read the full content of the email, including attachments")
```

## Compliance Standards

- **WCAG 2.1 AA**: 4.5:1 contrast ratio for normal text, 3:1 for large text
- **Section 508**: US government accessibility requirements
- **EN 301 549**: European accessibility standard

All features must pass these standards before release.