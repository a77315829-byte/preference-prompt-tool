### `FAQ.tsx`

```tsx
import { useState } from "react";
import type { ReactElement } from "react";
import "./theme.css";
import "./FAQ.css";

type FAQItem = {
  id: string;
  question: string;
  answer: string;
};

const faqItems: FAQItem[] = [
  {
    id: "faq-1",
    question: "서비스 이용은 무료인가요?",
    answer: "네, 서비스의 기본 기능은 무료로 이용할 수 있습니다.",
  },
  {
    id: "faq-2",
    question: "계정을 만들려면 어떻게 해야 하나요?",
    answer: "가입 페이지에서 이메일 주소와 비밀번호를 입력해 계정을 만들 수 있습니다.",
  },
  {
    id: "faq-3",
    question: "비밀번호를 잊어버렸어요. 어떻게 해야 하나요?",
    answer: "로그인 화면에서 비밀번호 재설정을 선택한 뒤 안내에 따라 진행해 주세요.",
  },
];

export default function FAQ(): ReactElement {
  const [openItems, setOpenItems] = useState<Set<string>>(() => new Set());

  const toggleItem = (id: string): void => {
    setOpenItems((currentItems) => {
      const nextItems = new Set(currentItems);

      if (nextItems.has(id)) {
        nextItems.delete(id);
      } else {
        nextItems.add(id);
      }

      return nextItems;
    });
  };

  return (
    <section className="faq" aria-labelledby="faq-title">
      <h2 className="faq__title" id="faq-title">
        자주 묻는 질문
      </h2>

      <div className="faq__list">
        {faqItems.map((item) => {
          const isOpen = openItems.has(item.id);
          const answerId = `${item.id}-answer`;

          return (
            <article className="faq__item" key={item.id}>
              <h3 className="faq__question-heading">
                <button
                  className="faq__question"
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={answerId}
                  onClick={() => toggleItem(item.id)}
                >
                  <span>{item.question}</span>
                  <span className="faq__icon" aria-hidden="true">
                    {isOpen ? "−" : "+"}
                  </span>
                </button>
              </h3>

              <div
                className="faq__answer"
                id={answerId}
                hidden={!isOpen}
              >
                <p>{item.answer}</p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
```

### `FAQ.css`

```css
.faq {
  width: 100%;
  max-width: var(--faq-max-width);
  margin: 0 auto;
  padding: var(--faq-space-xl) var(--faq-space-md);
  color: var(--faq-color-text);
  font-family: var(--faq-font-family);
}

.faq__title {
  margin: 0 0 var(--faq-space-lg);
  font-size: var(--faq-font-size-title);
  line-height: var(--faq-line-height);
}

.faq__list {
  border-top: 1px solid var(--faq-color-border);
}

.faq__item {
  border-bottom: 1px solid var(--faq-color-border);
}

.faq__question-heading {
  margin: 0;
}

.faq__question {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--faq-space-md);
  padding: var(--faq-space-md) 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  font-size: var(--faq-font-size-question);
  line-height: var(--faq-line-height);
  text-align: left;
}

.faq__question:focus-visible {
  outline: 2px solid var(--faq-color-focus);
  outline-offset: 4px;
}

.faq__icon {
  flex: 0 0 auto;
  color: var(--faq-color-accent);
  font-size: var(--faq-font-size-icon);
  line-height: 1;
}

.faq__answer {
  padding: 0 0 var(--faq-space-md);
  color: var(--faq-color-muted);
  font-size: var(--faq-font-size-answer);
  line-height: var(--faq-line-height);
}

.faq__answer[hidden] {
  display: none;
}

.faq__answer p {
  margin: 0;
}
```

### `theme.css`

```css
:root {
  --faq-max-width: 48rem;

  --faq-space-md: 1rem;
  --faq-space-lg: 1.5rem;
  --faq-space-xl: 2rem;

  --faq-font-family: Arial, sans-serif;
  --faq-font-size-title: 1.5rem;
  --faq-font-size-question: 1rem;
  --faq-font-size-answer: 0.9375rem;
  --faq-font-size-icon: 1.5rem;
  --faq-line-height: 1.6;

  --faq-color-text: #1f2937;
  --faq-color-muted: #4b5563;
  --faq-color-border: #d1d5db;
  --faq-color-accent: #2563eb;
  --faq-color-focus: #2563eb;
}
```

`FAQ`의 반환 타입을 `ReactElement`로 명시하고, 해당 타입을 타입 전용 import로 가져왔습니다. 그 외 동작과 스타일은 변경하지 않았습니다.