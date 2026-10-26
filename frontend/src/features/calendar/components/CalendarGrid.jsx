import React, { useEffect, useRef } from "react";
import { AlertTriangle } from "lucide-react";
import { addDays, dateKey, eventsForDay, STATUS_LABELS, timeLabel } from "../calendarDates";

function EventCard({ event, onOpen, compact = false, style }) {
  const staff = event.assigned_staff?.name || event.care_team.map(member => member.name).join(", ") || "Staff to be assigned";
  return <button type="button" style={style} className={`calendar-event calendar-event--${event.status.toLowerCase()} ${compact ? "calendar-event--compact" : ""}`}
    title={`${event.patient_name} · ${event.activity} · ${staff} · ${STATUS_LABELS[event.status]}`}
    onClick={() => onOpen(event.id)}>
    <span className="calendar-event-time">{timeLabel(event)} · {STATUS_LABELS[event.status]}{event.conflict_count > 0 && <AlertTriangle size={12} aria-label="Scheduling conflict" />}</span>
    <strong>{event.patient_name}</strong><span>{event.activity}</span><small>{staff}</small>
  </button>;
}

function timedLayout(events, day) {
  const start = new Date(`${dateKey(day)}T00:00:00`), end = addDays(start, 1);
  const timed = events.filter(event => !event.all_day).map(event => ({ event, start: Math.max(start.getTime(), new Date(event.starts_at).getTime()), end: Math.min(end.getTime(), new Date(event.ends_at).getTime()) })).sort((a, b) => a.start - b.start || b.end - a.end);
  const lanes = [];
  for (const item of timed) {
    let lane = lanes.findIndex(until => until <= item.start);
    if (lane === -1) lane = lanes.length;
    lanes[lane] = item.end;
    item.lane = lane;
  }
  return timed.map(item => {
    const startDate = new Date(item.start), endDate = new Date(item.end);
    const fromMinute = item.start === start.getTime() ? 0 : startDate.getHours() * 60 + startDate.getMinutes();
    const toMinute = item.end === end.getTime() ? 1440 : endDate.getHours() * 60 + endDate.getMinutes();
    return { ...item, style: { top: `${fromMinute / 60 * 72}px`, height: `${Math.max(42, (toMinute - fromMinute) / 60 * 72)}px`, left: `calc(${item.lane / lanes.length * 100}% + 3px)`, width: `calc(${100 / lanes.length}% - 6px)` } };
  });
}

export default function CalendarGrid({ view, days, events, anchor, onOpen, onDay }) {
  const scroll = useRef(null);
  useEffect(() => { if (scroll.current) scroll.current.scrollTop = events.some(event => event.all_day) ? 0 : 7 * 72; }, [view]);
  if (view === "month") return <div className="calendar-month-scroll"><div className="calendar-month" role="group" aria-label="Month calendar">
    {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(day => <div className="calendar-weekday" key={day}>{day}</div>)}
    {days.map(day => {
      const dayEvents = eventsForDay(events, day);
      return <section key={dateKey(day)} className={`calendar-month-day ${dateKey(day).slice(0, 7) !== anchor.slice(0, 7) ? "calendar-month-day--outside" : ""} ${dateKey(day) === dateKey(new Date()) ? "calendar-day--today" : ""}`} aria-label={day.toLocaleDateString([], { dateStyle: "full" })}>
        <button className="calendar-day-number" type="button" aria-label={`Open ${day.toLocaleDateString([], { dateStyle: "full" })}`} onClick={() => onDay(dateKey(day))}>{day.getDate()}</button>
        {dayEvents.slice(0, 3).map(event => <EventCard key={event.id} event={event} onOpen={onOpen} compact />)}
        {dayEvents.length > 3 && <button className="calendar-more" type="button" onClick={() => onDay(dateKey(day))}>+{dayEvents.length - 3} more activities</button>}
      </section>;
    })}
  </div></div>;
  const columns = { gridTemplateColumns: `56px repeat(${days.length}, minmax(${view === "week" ? 140 : 240}px, 1fr))` };
  return <div className="calendar-time-scroll" ref={scroll} tabIndex={0} aria-label={`${view} calendar, scroll to see all hours`}>
    <div className="calendar-time-inner" style={{ minWidth: view === "week" ? 1040 : 300 }}>
      <div className="calendar-time-head" style={columns}><div />{days.map(day => <button type="button" key={dateKey(day)} className={`calendar-time-date ${dateKey(day) === dateKey(new Date()) ? "calendar-day--today" : ""}`} onClick={() => onDay(dateKey(day))}>{day.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" })}</button>)}</div>
      <div className="calendar-all-day" style={columns}><span>Planned<br />/ due</span>{days.map(day => <div key={dateKey(day)}>{eventsForDay(events, day).filter(event => event.all_day).map(event => <EventCard key={event.id} event={event} onOpen={onOpen} compact />)}</div>)}</div>
      <div className="calendar-time-body" style={columns}>
        <div className="calendar-hours">{Array.from({ length: 24 }, (_, hour) => <span key={hour}>{String(hour).padStart(2, "0")}:00</span>)}</div>
        {days.map(day => <div className="calendar-time-day" key={dateKey(day)}>{timedLayout(eventsForDay(events, day), day).map(({ event, style }) => <EventCard key={event.id} event={event} onOpen={onOpen} style={style} />)}</div>)}
      </div>
    </div>
  </div>;
}
