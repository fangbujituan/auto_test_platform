import { describe, it, expect } from 'vitest'
import { validateEmail, validatePasswordLength, validatePasswordMatch } from './validators'

describe('validateEmail', () => {
  it('accepts valid email addresses', () => {
    expect(validateEmail('user@example.com')).toBe(true)
    expect(validateEmail('test@domain.org')).toBe(true)
    expect(validateEmail('a@b.c')).toBe(true)
  })

  it('rejects invalid email addresses', () => {
    expect(validateEmail('')).toBe(false)
    expect(validateEmail('no-at-sign')).toBe(false)
    expect(validateEmail('@missing-local.com')).toBe(false)
    expect(validateEmail('missing-domain@')).toBe(false)
    expect(validateEmail('has space@example.com')).toBe(false)
  })
})

describe('validatePasswordLength', () => {
  it('accepts passwords meeting minimum length', () => {
    expect(validatePasswordLength('123456')).toBe(true)
    expect(validatePasswordLength('abcdefgh')).toBe(true)
  })

  it('rejects passwords shorter than minimum length', () => {
    expect(validatePasswordLength('12345')).toBe(false)
    expect(validatePasswordLength('')).toBe(false)
  })

  it('supports custom minimum length', () => {
    expect(validatePasswordLength('abc', 3)).toBe(true)
    expect(validatePasswordLength('ab', 3)).toBe(false)
  })

  it('rejects non-string values', () => {
    expect(validatePasswordLength(null)).toBe(false)
    expect(validatePasswordLength(undefined)).toBe(false)
  })
})

describe('validatePasswordMatch', () => {
  it('returns true when passwords match', () => {
    expect(validatePasswordMatch('abc123', 'abc123')).toBe(true)
  })

  it('returns false when passwords differ', () => {
    expect(validatePasswordMatch('abc123', 'xyz789')).toBe(false)
  })

  it('is case-sensitive', () => {
    expect(validatePasswordMatch('Password', 'password')).toBe(false)
  })
})
