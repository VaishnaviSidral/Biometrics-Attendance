import { useState, useCallback, useEffect } from 'react';
import {
    getCurrentISOWeek,
} from '../utils/isoWeek';
/**
 * Per-view session-based date management.
 * Each admin view (Dashboard, AllEmployees, IndividualReport, MonthlyReport)
 * stores its own date selection independently in sessionStorage.
 *
 * Usage:
 *   const { weekYear, weekValue, setWeekYear, setWeekValue } = useViewWeekDate('dashboard');
 *   const { monthYear, monthValue, ... } = useViewMonthDate('individualReport');
 */

// ── Defaults ──────────────────────────────────────────────

function getDefaultWeek() {
    const currentISO = getCurrentISOWeek();
    return {
        year: currentISO.year,
        weekValue: `${currentISO.year}-W${String(currentISO.week).padStart(2, '0')}`,
    };
}

function getDefaultMonth() {
    const now = new Date();
    return {
        year: now.getFullYear(),
        month: now.getMonth() + 1, // 1-12
    };
}

// ── Hook: Per-view Year-Month-Week Date ──────────────────────

export function useViewYearMonthWeekDate(viewKey) {
    const PREFIX = `date_${viewKey}`;

    const [year, setYearState] = useState(() => {
        const saved = localStorage.getItem(`${PREFIX}_year`);
        return saved ? Number(saved) : getDefaultWeek().year;
    });

    const [month, setMonthState] = useState(() => {
        const saved = sessionStorage.getItem(`${PREFIX}_month`);
        return saved ? Number(saved) : new Date().getMonth() + 1;
    });

    const [weekValue, setWeekValueState] = useState(() => {
        const saved = sessionStorage.getItem(`${PREFIX}_week_value`);
        return saved || getDefaultWeek().weekValue;
    });

    const setYear = useCallback((newYear) => {
        setYearState(newYear);
        localStorage.setItem(`${PREFIX}_year`, String(newYear));
    }, [PREFIX]);

    const setMonth = useCallback((newMonth) => {
        setMonthState(newMonth);
        localStorage.setItem(`${PREFIX}_month`, String(newMonth));
    }, [PREFIX]);

    const setWeekValue = useCallback((newWeekValue) => {
        setWeekValueState(newWeekValue);
        localStorage.setItem(`${PREFIX}_week_value`, newWeekValue);
    }, [PREFIX]);

    return { year, month, weekValue, setYear, setMonth, setWeekValue };
}

// ── Hook: Per-view Week Date ──────────────────────────────

export function useViewWeekDate(viewKey) {
    const PREFIX = `date_${viewKey}`;

    const [weekYear, setWeekYearState] = useState(() => {
        const saved = sessionStorage.getItem(`${PREFIX}_week_year`);
        return saved ? Number(saved) : getDefaultWeek().year;
    });

    const [weekValue, setWeekValueState] = useState(() => {
        const saved = sessionStorage.getItem(`${PREFIX}_week_value`);
        return saved || getDefaultWeek().weekValue;
    });

    const setWeekYear = useCallback((year) => {
        setWeekYearState(year);
        localStorage.setItem(`${PREFIX}_week_year`, String(year));
    }, [PREFIX]);

    const setWeekValue = useCallback((value) => {
        setWeekValueState(value);
        localStorage.setItem(`${PREFIX}_week_value`, value);
    }, [PREFIX]);

    return { weekYear, weekValue, setWeekYear, setWeekValue };
}

// ── Hook: Per-view Month Date ─────────────────────────────

export function useViewMonthDate(viewKey) {
    const PREFIX = `date_${viewKey}`;

    const [monthYear, setMonthYearState] = useState(() => {
        const saved = sessionStorage.getItem(`${PREFIX}_month_year`);
        return saved ? Number(saved) : getDefaultMonth().year;
    });

    const [monthValue, setMonthValueState] = useState(() => {
        const saved = sessionStorage.getItem(`${PREFIX}_month_value`);
        return saved ? Number(saved) : getDefaultMonth().month;
    });

    const setMonthYear = useCallback((year) => {
        setMonthYearState(year);
        localStorage.setItem(`${PREFIX}_month_year`, String(year));
    }, [PREFIX]);

    const setMonthValue = useCallback((month) => {
        setMonthValueState(month);
        localStorage.setItem(`${PREFIX}_month_value`, String(month));
    }, [PREFIX]);

    // Combined month string for API calls (e.g., "2026-02")
    const monthString = `${monthYear}-${String(monthValue).padStart(2, '0')}`;

    // Set month from a YYYY-MM string
    const setMonthString = useCallback((str) => {
        if (!str) return;
        const [y, m] = str.split('-').map(Number);
        if (y && m) {
            setMonthYear(y);
            setMonthValue(m);
        }
    }, [setMonthYear, setMonthValue]);

    return { monthYear, monthValue, monthString, setMonthYear, setMonthValue, setMonthString };
}

function getDefaultDate() {
    const iso = getCurrentISOWeek();
    const now = new Date();

    return {
        year: iso.year,
        month: now.getMonth() + 1,
        week: `${iso.year}-W${String(iso.week).padStart(2, '0')}`
    };
}

export function useGlobalDate() {

    const defaults = getDefaultDate();

    const [year, setYearState] = useState(() => {
        return Number(sessionStorage.getItem('attendance_year')) || defaults.year;
    });

    const [month, setMonthState] = useState(() => {
        return Number(sessionStorage.getItem('attendance_month')) || defaults.month;
    });

    const [week, setWeekState] = useState(() => {
        const saved = sessionStorage.getItem('attendance_week');
        return saved || defaults.week;
    });

    // ✅ Ensure default week is stored when first loading
    useEffect(() => {
        if (!sessionStorage.getItem('attendance_week')) {
            sessionStorage.setItem('attendance_week', defaults.week);
            setWeekState(defaults.week);
        }
    }, [defaults.week]);

    const setYear = useCallback((value) => {
        setYearState(value);
        sessionStorage.setItem('attendance_year', value);
    }, []);

    const setMonth = useCallback((value) => {
        setMonthState(value);
        sessionStorage.setItem('attendance_month', value);
    }, []);

    const setWeek = useCallback((value) => {
        setWeekState(value);
        sessionStorage.setItem('attendance_week', value);
    }, []);

    return {
        year,
        month,
        week,
        setYear,
        setMonth,
        setWeek
    };
}