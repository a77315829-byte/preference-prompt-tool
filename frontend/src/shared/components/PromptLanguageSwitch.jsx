// 최종 프롬프트 언어 전환. 서버가 언어별 프롬프트(prompts)를 한 번에 주므로
// 바꿀 때 요청을 다시 보내지 않는다. 언어가 하나뿐이면(템플릿, 최적화 결과) 그리지 않는다.
const LABELS = { en: 'English', ko: '한국어' };

export default function PromptLanguageSwitch({ languages, value, onChange }) {
  if (!languages || languages.length < 2) return null;
  return (
    <div className="prompt-language-switch" role="group" aria-label="프롬프트 언어">
      {languages.map((language) => (
        <button
          key={language}
          type="button"
          className={language === value ? 'is-active' : ''}
          aria-pressed={language === value}
          onClick={() => onChange(language)}
        >
          {LABELS[language] || language}
        </button>
      ))}
    </div>
  );
}
