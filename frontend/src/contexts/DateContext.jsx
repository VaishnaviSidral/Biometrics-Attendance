import { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import {
    getCurrentISOWeek,
    getWeeksInMonth,
} from '../utils/isoWeek';

// ── Global Date Context ──────────────────────────────────────

const DateContext = createContext(null);

function getDefaults() {
    const iso = getCurrentISOWeek();
    const now = new Date();
    return {
        year: iso.year,
        month: now.getMonth() + 1,
        week: `${iso.year}-W${String(iso.week).padStart(2, '0')}`,
    };
}

export function DateProvider({ children }) {
    const defaults = getDefaults();

    const [year, setYearState] = useState(() => {
        return Number(sessionStorage.getItem('global_date_year')) || defaults.year;
    });

    const [month, setMonthState] = useState(() => {
        return Number(sessionStorage.getItem('global_date_month')) || defaults.month;
    });

    const [week, setWeekState] = useState(() => {
        return sessionStorage.getItem('global_date_week') || defaults.week;
    });

    const setYear = useCallback((value) => {
        setYearState(value);
        sessionStorage.setItem('global_date_year', String(value));
    }, []);

    const setMonth = useCallback((value) => {
        setMonthState(value);
        sessionStorage.setItem('global_date_month', String(value));
    }, []);

    const setWeek = useCallback((value) => {
        setWeekState(value);
        sessionStorage.setItem('global_date_week', value);
    }, []);

    // Auto-correct week when year/month changes so it stays valid
    useEffect(() => {
        const weeksInMonth = getWeeksInMonth(year, month);
        const isWeekValid = weeksInMonth.some(w => w.value === week);
        if (!isWeekValid && weeksInMonth.length > 0) {
            const corrected = weeksInMonth[0].value;
            setWeekState(corrected);
            sessionStorage.setItem('global_date_week', corrected);
        }
    }, [year, month, week]);

    const value = useMemo(() => ({
        year, month, week, setYear, setMonth, setWeek,
    }), [year, month, week, setYear, setMonth, setWeek]);

    return (
        <DateContext.Provider value={value}>
            {children}
        </DateContext.Provider>
    );
}

export function useGlobalDate() {
    const ctx = useContext(DateContext);
    if (!ctx) throw new Error('useGlobalDate must be used within DateProvider');
    return ctx;
}
