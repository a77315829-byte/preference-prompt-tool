import { useId, useRef, useState, type KeyboardEvent } from 'react';

export type Item = { id: string; title: string; body: string; disabled?: boolean };
export type Props = { items: Item[] };

export function Component({ items }: Props) {
  const [openId, setOpenId] = useState<string | null>(null);
  const buttons = useRef<Array<HTMLButtonElement | null>>([]);
  const prefix = useId();
  function navigate(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const enabled = items.map((item, position) => item.disabled ? -1 : position).filter(position => position >= 0);
    const position = enabled.indexOf(index);
    let next: number;
    if (event.key === 'ArrowDown') next = enabled[(position + 1) % enabled.length];
    else if (event.key === 'ArrowUp') next = enabled[(position - 1 + enabled.length) % enabled.length];
    else if (event.key === 'Home') next = enabled[0];
    else if (event.key === 'End') next = enabled[enabled.length - 1];
    else return;
    event.preventDefault();
    buttons.current[next]?.focus();
  }
  return <section aria-label="Help topics">{items.map((item, index) => {
    const open = openId === item.id;
    const triggerId = `${prefix}-trigger-${item.id}`;
    const panelId = `${prefix}-panel-${item.id}`;
    return <div key={item.id}>
      <h3><button type="button" disabled={item.disabled} id={triggerId} ref={node => { buttons.current[index] = node; }} aria-expanded={open} aria-controls={panelId}
        onClick={() => setOpenId(open ? null : item.id)} onKeyDown={event => navigate(event, index)}>{item.title}</button></h3>
      {open && <div role="region" id={panelId} aria-labelledby={triggerId}>{item.body}</div>}
    </div>;
  })}</section>;
}
