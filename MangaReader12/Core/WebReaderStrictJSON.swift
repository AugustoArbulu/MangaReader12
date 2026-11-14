import Foundation

/// A bounded, strict JSON preflight used before Foundation parses signed
/// update documents. JSONSerialization silently accepts duplicate object
/// keys, which may make two verifiers interpret the same bytes differently.
/// This validates syntax and rejects duplicate *decoded* keys at every depth.
/// It does not interpret or trust update metadata or verify signatures.
enum WebReaderStrictJSON {
    static func accepts(_ data: Data) -> Bool {
        guard !data.isEmpty, data.count <= 64 * 1024 else { return false }
        var parser = Parser(bytes: Array(data))
        return parser.parseDocument()
    }

    private struct Parser {
        let bytes: [UInt8]
        var offset = 0
        var nodeCount = 0

        private var atEnd: Bool { return offset >= bytes.count }
        private var current: UInt8? { return atEnd ? nil : bytes[offset] }

        mutating func parseDocument() -> Bool {
            skipWhitespace()
            guard readValue(depth: 0) else { return false }
            skipWhitespace()
            return atEnd
        }

        private mutating func skipWhitespace() {
            while let value = current,
                value == 0x20 || value == 0x09 || value == 0x0A || value == 0x0D {
                offset += 1
            }
        }

        private mutating func consume(_ byte: UInt8) -> Bool {
            guard current == byte else { return false }
            offset += 1
            return true
        }

        private mutating func readValue(depth: Int) -> Bool {
            guard depth <= 32, nodeCount < 4096 else { return false }
            nodeCount += 1
            skipWhitespace()
            guard let value = current else { return false }
            switch value {
            case 0x7B: return readObject(depth: depth + 1) // {
            case 0x5B: return readArray(depth: depth + 1)  // [
            case 0x22: return readString() != nil
            case 0x74: return consumeLiteral([0x74, 0x72, 0x75, 0x65])  // true
            case 0x66: return consumeLiteral([0x66, 0x61, 0x6C, 0x73, 0x65]) // false
            case 0x6E: return consumeLiteral([0x6E, 0x75, 0x6C, 0x6C]) // null
            case 0x2D, 0x30...0x39: return readNumber()
            default: return false
            }
        }

        private mutating func readObject(depth: Int) -> Bool {
            guard consume(0x7B) else { return false }
            skipWhitespace()
            if consume(0x7D) { return true }
            var names = Set<String>()
            while true {
                skipWhitespace()
                guard let name = readString(), names.insert(name).inserted else {
                    return false
                }
                skipWhitespace()
                guard consume(0x3A), readValue(depth: depth) else { return false }
                skipWhitespace()
                if consume(0x7D) { return true }
                guard consume(0x2C) else { return false }
            }
        }

        private mutating func readArray(depth: Int) -> Bool {
            guard consume(0x5B) else { return false }
            skipWhitespace()
            if consume(0x5D) { return true }
            while true {
                guard readValue(depth: depth) else { return false }
                skipWhitespace()
                if consume(0x5D) { return true }
                guard consume(0x2C) else { return false }
            }
        }

        private mutating func readString() -> String? {
            let start = offset
            guard consume(0x22) else { return nil }
            while let byte = current {
                offset += 1
                if byte == 0x22 {
                    return try? JSONDecoder().decode(
                        String.self, from: Data(bytes[start..<offset])
                    )
                }
                if byte < 0x20 { return nil }
                if byte == 0x5C { // Backslash
                    guard let escaped = current else { return nil }
                    offset += 1
                    if escaped == 0x75 { // Unicode escape: exactly four hex digits
                        for _ in 0..<4 {
                            guard let hex = current,
                                (hex >= 0x30 && hex <= 0x39) ||
                                (hex >= 0x41 && hex <= 0x46) ||
                                (hex >= 0x61 && hex <= 0x66) else { return nil }
                            offset += 1
                        }
                    } else if ![0x22, 0x5C, 0x2F, 0x62, 0x66, 0x6E,
                                0x72, 0x74].contains(escaped) {
                        return nil
                    }
                }
            }
            return nil
        }

        private mutating func consumeLiteral(_ literal: [UInt8]) -> Bool {
            guard bytes.count - offset >= literal.count else { return false }
            for character in literal {
                guard consume(character) else { return false }
            }
            return true
        }

        private mutating func readNumber() -> Bool {
            _ = consume(0x2D) // optional minus
            if !consume(0x30) {
                guard let first = current, first >= 0x31 && first <= 0x39 else {
                    return false
                }
                offset += 1
                while let digit = current, digit >= 0x30 && digit <= 0x39 {
                    offset += 1
                }
            }
            if consume(0x2E) { // fractional part
                var consumed = false
                while let digit = current, digit >= 0x30 && digit <= 0x39 {
                    offset += 1
                    consumed = true
                }
                if !consumed { return false }
            }
            if consume(0x65) || consume(0x45) {
                if !consume(0x2B) { _ = consume(0x2D) }
                var consumed = false
                while let digit = current, digit >= 0x30 && digit <= 0x39 {
                    offset += 1
                    consumed = true
                }
                if !consumed { return false }
            }
            return true
        }
    }
}
