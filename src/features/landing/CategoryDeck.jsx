import { motion, useReducedMotion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';

export default function CategoryDeck({ options, selectedCategory, onSelect, onContinue }) {
  const index = Math.max(0, options.findIndex(({ id }) => id === selectedCategory));
  const selected = options[index];
  const viewport = useRef(null);
  const pointer = useRef(null);
  const dragged = useRef(false);
  const [dragX, setDragX] = useState(0);
  const reducedMotion = useReducedMotion();
  const selectRelative = (step) => onSelect(options[(index + step + options.length) % options.length].id);

  useEffect(() => {
    let total = 0;
    let locked = false;
    let reset;
    const handleWheel = (event) => {
      event.preventDefault();
      event.stopPropagation();
      clearTimeout(reset);
      reset = setTimeout(() => { total = 0; locked = false; }, 180);
      if (locked) return;
      total += (Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY)
        * (event.deltaMode === 1 ? 16 : 1);
      if (Math.abs(total) < 45) return;
      locked = true;
      const current = options.findIndex(({ id }) => id === viewport.current.dataset.selected);
      onSelect(options[(current + Math.sign(total) + options.length) % options.length].id);
    };
    const element = viewport.current;
    element.addEventListener('wheel', handleWheel, { passive: false });
    return () => { element.removeEventListener('wheel', handleWheel); clearTimeout(reset); };
  }, [options, onSelect]);

  const endDrag = (event, cancelled = false) => {
    if (!pointer.current) return;
    const delta = event.clientX - pointer.current.x;
    if (!cancelled && dragged.current && Math.abs(delta) > 45) selectRelative(delta < 0 ? 1 : -1);
    pointer.current = null;
    setDragX(0);
  };

  return (
    <div className="category-deck" role="region" aria-roledescription="캐러셀" aria-label="카테고리 선택"
      onKeyDown={(event) => {
        const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
        if (step) { event.preventDefault(); event.stopPropagation(); selectRelative(step); }
        if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault(); onSelect(options[event.key === 'Home' ? 0 : options.length - 1].id);
        }
      }}>
      <div className="category-deck-viewport" ref={viewport} data-selected={selected.id}
        onPointerDown={(event) => {
          if (event.button !== 0 || !event.isPrimary) return;
          dragged.current = false;
          pointer.current = { x: event.clientX };
        }}
        onPointerMove={(event) => {
          if (!pointer.current) return;
          const delta = event.clientX - pointer.current.x;
          if (Math.abs(delta) > 8) {
            dragged.current = true;
            event.currentTarget.setPointerCapture(event.pointerId);
            setDragX(Math.max(-100, Math.min(100, delta)));
          }
        }}
        onPointerUp={endDrag} onPointerCancel={(event) => endDrag(event, true)}
        onLostPointerCapture={() => { pointer.current = null; setDragX(0); }}
        onClickCapture={(event) => {
          if (dragged.current && event.detail !== 0) { event.preventDefault(); event.stopPropagation(); }
        }}>
        {options.map((category, cardIndex) => {
          const offset = ((cardIndex - index + options.length + options.length / 2) % options.length) - options.length / 2;
          const active = offset === 0;
          return (
            <motion.button key={category.id} type="button"
              className={`category-card category-card-${category.accent} ${active ? 'is-selected' : ''}`}
              aria-label={category.title} aria-pressed={active} aria-hidden={Math.abs(offset) > 2}
              tabIndex={active ? 0 : -1} onClick={() => onSelect(category.id)}
              initial={false}
              animate={{ x: `calc(${offset * 68}% + ${dragX}px)`, y: Math.abs(offset) * 12,
                rotate: offset * 3, scale: 1 - Math.min(Math.abs(offset), 3) * 0.09,
                opacity: Math.abs(offset) > 2 ? 0 : active ? 1 : 0.65 }}
              transition={reducedMotion || dragX ? { duration: 0 } : { type: 'spring', stiffness: 310, damping: 32 }}
              style={{ zIndex: 5 - Math.abs(offset), pointerEvents: Math.abs(offset) > 2 ? 'none' : 'auto' }}>
              <div className="category-card-topline"><span>{category.number}</span><span>{category.label}</span></div>
              <div className="category-card-copy"><h3>{category.title}</h3><p>{category.description}</p></div>
              <span className="category-arrow" aria-hidden="true">{active ? '✓' : '↗'}</span>
            </motion.button>
          );
        })}
      </div>
      <div className="category-deck-controls">
        <button type="button" aria-label="이전 카테고리" onClick={() => selectRelative(-1)}>←</button>
        <div className="category-deck-dots" aria-label="카테고리 바로 선택">
          {options.map((category) => <button key={category.id} type="button"
            aria-label={`${category.title} 선택`} aria-pressed={selected.id === category.id}
            title={category.title} onClick={() => onSelect(category.id)}><span /></button>)}
        </div>
        <button type="button" aria-label="다음 카테고리" onClick={() => selectRelative(1)}>→</button>
      </div>
      <div className="category-selection">
        <p role="status" aria-live="polite"><span className="category-count">{String(index + 1).padStart(2, '0')} / {String(options.length).padStart(2, '0')}</span><strong>{selected.title}</strong></p>
        <button className="selection-button" type="button" onClick={onContinue}>
          {selected.id === 'idleTracker' ? '비용 점검 시작하기' : '선택 비교 시작하기'}<span aria-hidden="true">→</span>
        </button>
      </div>
    </div>
  );
}
