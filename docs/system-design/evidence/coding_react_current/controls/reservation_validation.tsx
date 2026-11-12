import { useState, type FormEvent } from 'react';

export type Reservation = { start: string; end: string; guests: number };
export type Props = { capacity: number; onReserve: (reservation: Reservation) => void };

export function Component({ capacity, onReserve }: Props) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [guests, setGuests] = useState('');
  const [errors, setErrors] = useState({ start: '', end: '', guests: '' });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const count = Number(guests);
    const next = {
      start: start ? '' : 'Start date is required',
      end: !end ? 'End date is required' : start && end <= start ? 'End must follow start' : '',
      guests: guests.trim() === '' || !Number.isInteger(count) || count < 1 || count > capacity ? 'Invalid guest count' : '',
    };
    setErrors(next);
    if (!Object.values(next).some(Boolean)) onReserve({ start, end, guests: count });
  }
  return <form aria-label="Reservation" noValidate onSubmit={submit}>
    <label>Start date<input type="date" value={start} aria-invalid={Boolean(errors.start)} onChange={event => setStart(event.currentTarget.value)} /></label>
    <label>End date<input type="date" value={end} aria-invalid={Boolean(errors.end)} onChange={event => setEnd(event.currentTarget.value)} /></label>
    <label>Guests<input type="number" step="any" value={guests} aria-invalid={Boolean(errors.guests)} onChange={event => setGuests(event.currentTarget.value)} /></label>
    {Object.values(errors).some(Boolean) && <p role="alert">{Object.values(errors).filter(Boolean).join('. ')}</p>}
    <button type="submit">Reserve</button>
  </form>;
}
