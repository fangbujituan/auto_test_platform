import { parseCurl } from './curlParser.js'

// The actual string the user pastes from browser DevTools contains literal \" characters
// In the source code, we need to represent the literal backslash-quote as \\\"
// But the key insight: when user pastes from DevTools, the string contains literal backslash + quote

// Test 1: The actual curl command as it appears when copied from DevTools (bash format)
// The literal string contains: --data-raw "{\"ClientID\":1005,\"PageIndex\":1}"
// In JS source, to get a literal backslash we need \\, so \" becomes \\"
const curl1 = 'curl -X POST "https://example.com/api" --data-raw "{\\"ClientID\\":1005,\\"PageIndex\\":1}"'
console.log('Test 1 input:', curl1)
const r1 = parseCurl(curl1)
console.log('Test 1 body:', JSON.stringify(r1.body))
console.log('Test 1 body_type:', r1.body_type)
console.log('---')

// Test 2: empty string values
const curl2 = 'curl -X POST "https://example.com/api" --data-raw "{\\"sortfield\\":\\"\\",\\"sorttype\\":\\"\\"}"'
console.log('Test 2 input:', curl2)
const r2 = parseCurl(curl2)
console.log('Test 2 body:', JSON.stringify(r2.body))
console.log('Test 2 body_type:', r2.body_type)
console.log('---')

// Test 3: -d flag
const curl3 = 'curl -X POST "https://example.com/api" -d "{\\"name\\":\\"test\\"}"'
console.log('Test 3 input:', curl3)
const r3 = parseCurl(curl3)
console.log('Test 3 body:', JSON.stringify(r3.body))
console.log('Test 3 body_type:', r3.body_type)
