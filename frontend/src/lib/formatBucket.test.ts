import { formatBucket } from './formatBucket'

describe('formatBucket', () => {
  describe('day', () => {
    it('formats a mid-month day', () => {
      expect(formatBucket('2026-06-15', 'day')).toBe('Jun 15')
    })

    it('strips leading zero from day', () => {
      expect(formatBucket('2026-01-03', 'day')).toBe('Jan 3')
    })

    it('formats December 31 (year boundary)', () => {
      expect(formatBucket('2025-12-31', 'day')).toBe('Dec 31')
    })

    it('formats January 1 (year boundary)', () => {
      expect(formatBucket('2026-01-01', 'day')).toBe('Jan 1')
    })
  })

  describe('week', () => {
    it('formats a standard week', () => {
      expect(formatBucket('2026-23', 'week')).toBe('W23')
    })

    it('formats single-digit week', () => {
      expect(formatBucket('2026-05', 'week')).toBe('W5')
    })

    it('handles week 0 (SQLite week of Jan 1 before first Monday)', () => {
      expect(formatBucket('2026-00', 'week')).toBe('2026 W1')
    })
  })

  describe('month', () => {
    it('formats a standard month', () => {
      expect(formatBucket('2026-06', 'month')).toBe('Jun 2026')
    })

    it('formats January', () => {
      expect(formatBucket('2026-01', 'month')).toBe('Jan 2026')
    })

    it('formats December', () => {
      expect(formatBucket('2025-12', 'month')).toBe('Dec 2025')
    })
  })

  describe('quarter', () => {
    it('formats Q1', () => {
      expect(formatBucket('2026-1', 'quarter')).toBe('Q1 2026')
    })

    it('formats Q4', () => {
      expect(formatBucket('2025-4', 'quarter')).toBe('Q4 2025')
    })
  })
})
