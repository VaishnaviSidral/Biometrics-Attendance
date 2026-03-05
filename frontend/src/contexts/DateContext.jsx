import { useState, useCallback } from 'react';
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
        const saved = sessionStorage.getItem(`${PREFIX}_year`);
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
        sessionStorage.setItem(`${PREFIX}_year`, String(newYear));
    }, [PREFIX]);

    const setMonth = useCallback((newMonth) => {
        setMonthState(newMonth);
        sessionStorage.setItem(`${PREFIX}_month`, String(newMonth));
    }, [PREFIX]);

    const setWeekValue = useCallback((newWeekValue) => {
        setWeekValueState(newWeekValue);
        sessionStorage.setItem(`${PREFIX}_week_value`, newWeekValue);
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
        sessionStorage.setItem(`${PREFIX}_week_year`, String(year));
    }, [PREFIX]);

    const setWeekValue = useCallback((value) => {
        setWeekValueState(value);
        sessionStorage.setItem(`${PREFIX}_week_value`, value);
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
        sessionStorage.setItem(`${PREFIX}_month_year`, String(year));
    }, [PREFIX]);

    const setMonthValue = useCallback((month) => {
        setMonthValueState(month);
        sessionStorage.setItem(`${PREFIX}_month_value`, String(month));
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
