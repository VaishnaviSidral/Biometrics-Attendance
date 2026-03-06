/**
 * ISO Week Calendar Utilities
 *
 * All week generation is calendar-based — never depends on DB or uploaded data.
 * ISO 8601: Week 1 is the week containing the year's first Thursday.
 * Weeks start on Monday.
 */

/**
 * Get ISO week number for a given date.
 */
export function getISOWeekNumber(d) {
    const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    const dayNum = date.getUTCDay() || 7; // Sunday = 7
    date.setUTCDate(date.getUTCDate() + 4 - dayNum); // nearest Thursday
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil(((date - yearStart) / 86400000 + 1) / 7);
}

/**
 * Get ISO year for a date (may differ from calendar year near year boundaries).
 */
export function getISOYear(d) {
    const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    const dayNum = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - dayNum);
    return date.getUTCFullYear();
}

/**
 * Get Monday of ISO week 1 for a given ISO year.
 */
function getISOWeek1Monday(year) {
    // Jan 4 is always in ISO week 1
    const jan4 = new Date(Date.UTC(year, 0, 4));
    const dow = jan4.getUTCDay() || 7; // Mon=1 … Sun=7
    const monday = new Date(jan4);
    monday.setUTCDate(jan4.getUTCDate() - (dow - 1));
    return monday;
}

/**
 * Get the Monday date for a given ISO year + week.
 */
export function getISOWeekMonday(year, week) {
    const w1 = getISOWeek1Monday(year);
    const monday = new Date(w1);
    monday.setUTCDate(w1.getUTCDate() + (week - 1) * 7);
    return monday;
}

/**
 * Total ISO weeks in a year (52 or 53).
 */
export function getISOWeeksInYear(year) {
    const dec28 = new Date(Date.UTC(year, 11, 28));
    return getISOWeekNumber(dec28);
}

/**
 * Current ISO year + week.
 * @returns {{ year: number, week: number }}
 */
export function getCurrentISOWeek() {
    const today = new Date();
    return { year: getISOYear(today), week: getISOWeekNumber(today) };
}

/**
 * Format a UTC date as "Feb 17, 2026".
 */
function fmtShort(d) {
    return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'UTC',
    });
}

/**
 * Generate ALL ISO weeks for a given year.
 *
 * @param {number} year
 * @returns {Array<{ value: string, label: string, weekStart: string, weekEnd: string }>}
 *   value    = "2026-W08"
 *   label    = "Week 08 (Feb 17 – Feb 23, 2026)"
 *   weekStart = "2026-02-17"  (YYYY-MM-DD, Monday)
 *   weekEnd   = "2026-02-23"  (YYYY-MM-DD, Sunday)
 */
export function generateISOWeeks(year) {
    const total = getISOWeeksInYear(year);
    const weeks = [];

    for (let w = 1; w <= total; w++) {
        const monday = getISOWeekMonday(year, w);
        const sunday = new Date(monday);
        sunday.setUTCDate(monday.getUTCDate() + 6);

        weeks.push({
            value: `${year}-W${String(w).padStart(2, '0')}`,
            label: `Week ${String(w).padStart(2, '0')} (${fmtShort(monday)} – ${fmtShort(sunday)})`,
            weekStart: monday.toISOString().split('T')[0],
            weekEnd: sunday.toISOString().split('T')[0],
        });
    }

    return weeks;
}

/**
 * Parse "2026-W08" → { year: 2026, week: 8 }  or null.
 */
export function parseISOWeek(weekString) {
    if (!weekString) return null;
    const m = weekString.match(/^(\d{4})-W(\d{1,2})$/);
    if (!m) return null;
    return { year: parseInt(m[1], 10), week: parseInt(m[2], 10) };
}

/**
 * Convert "2026-W08" → "2026-02-17" (Monday date string).
 */
export function isoWeekToDateString(weekString) {
    const p = parseISOWeek(weekString);
    if (!p) return null;
    return getISOWeekMonday(p.year, p.week).toISOString().split('T')[0];
}

/**
 * Get the previous `count` ISO weeks before `weekString` (not including it).
 * Cross-year safe.
 *
 * @param {string} weekString  e.g. "2026-W08"
 * @param {number} count
 * @returns {string[]}  e.g. ["2026-W07", "2026-W06", …]
 */
export function getPreviousISOWeeks(weekString, count) {
    const p = parseISOWeek(weekString);
    if (!p) return [];

    const result = [];
    let { year, week } = p;

    for (let i = 0; i < count; i++) {
        week--;
        if (week < 1) {
            year--;
            week = getISOWeeksInYear(year);
        }
        result.push(`${year}-W${String(week).padStart(2, '0')}`);
    }

    return result;
}

/**
 * Build year range array for dropdowns.
 * currentYear - 2  →  currentYear + 1
 */
export function getYearRange() {
    const currentYear = new Date().getFullYear();
    const years = [];
    for (let y = currentYear - 2; y <= currentYear + 1; y++) {
        years.push(y);
    }
    return years;
}

/**
 * Get weeks in a specific month
 * @param {number} year
 * @param {number} month (1-12)
 * @returns {Array<{ value: string, label: string, weekStart: string, weekEnd: string }>}
 */
export function getWeeksInMonth(year, month) {
    const weeks = [];

    const firstDay = new Date(Date.UTC(year, month - 1, 1));
    const lastDay = new Date(Date.UTC(year, month, 0));

    // Find Monday of the week containing the 1st
    let currentMonday = new Date(firstDay);
    const dayOfWeek = currentMonday.getUTCDay() || 7; // Sun=7
    currentMonday.setUTCDate(currentMonday.getUTCDate() - (dayOfWeek - 1));

    while (currentMonday <= lastDay) {
        const sunday = new Date(currentMonday);
        sunday.setUTCDate(currentMonday.getUTCDate() + 6);

        if (sunday >= firstDay && currentMonday <= lastDay) {
            const weekNum = getISOWeekNumber(currentMonday);
            const isoYear = getISOYear(currentMonday);

            weeks.push({
                value: `${isoYear}-W${String(weekNum).padStart(2, '0')}`,
                label: `Week ${String(weekNum).padStart(2, '0')} (${fmtShort(currentMonday)} – ${fmtShort(sunday)})`,
                weekStart: currentMonday.toISOString().split('T')[0],
                weekEnd: sunday.toISOString().split('T')[0],
            });
        }

        currentMonday.setUTCDate(currentMonday.getUTCDate() + 7);
    }

    return weeks;
}
/**
 * Get month names array
 * @returns {string[]}
 */
export function getMonthNames() {
    return [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
}




