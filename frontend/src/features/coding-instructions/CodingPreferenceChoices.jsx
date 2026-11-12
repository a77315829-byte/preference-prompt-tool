import { CODING_CHOICES } from './codingOptions';

const DESCRIPTIONS = {
  explanation: { brief: '코드와 핵심 이유를 빠르게 확인해요.', steps: '과정과 이유를 순서대로 이해해요.' },
  comments: { essential: '코드로 충분한 내용은 반복하지 않아요.', detailed: '핵심 로직의 의도를 함께 읽어요.' },
  structure: { compact: '작은 작업은 한곳에서 바로 확인해요.', modular: '역할별 함수와 파일로 나눠 봐요.' },
  output: { complete: '필요한 파일의 전체 코드를 받아요.', changes: '기존 코드에서 바뀐 위치를 중심으로 봐요.' },
};

export default function CodingPreferenceChoices({ profile, onSelect, readOnly = false, busy = false }) {
  return <div className="coding-preference-choices">
    {Object.entries(CODING_CHOICES).map(([key, field], index) => {
      const selected = profile.preferences[key];
      const compared = profile.comparison && profile.comparison.choices[key] !== null;
      return <section key={key} className={`coding-preference-choice tone-${['lavender', 'peach', 'mint', 'blue'][index]}`}>
        <div className="coding-preference-title"><span className="coding-choice-number">0{index + 1}</span><h4>{field.label}</h4>
          <span className="coding-choice-origin">{!selected ? '선택 필요' : compared ? '예시에서 골랐어요' : '직접 골랐어요'}</span></div>
        {readOnly ? <div className="coding-choice-answer"><strong>{field.options[selected]}</strong><p>{DESCRIPTIONS[key][selected]}</p></div>
          : <div role="group" aria-label={`${field.label} 선택`} className="coding-preference-buttons">
            {Object.entries(field.options).map(([value, label]) => <button key={value} type="button" disabled={busy}
              aria-label={`${field.label}: ${label}`} aria-pressed={selected === value} onClick={() => onSelect(key, value)}>
              <span><strong>{label}</strong><small>{DESCRIPTIONS[key][value]}</small></span><span aria-hidden="true">{selected === value ? '✓' : '○'}</span>
            </button>)}
          </div>}
      </section>;
    })}
  </div>;
}
