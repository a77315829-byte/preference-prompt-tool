import { CODING_CHOICES } from './codingOptions';

export default function CodingSignalSummary({ comparison, resolved = false }) {
  if (![3, 4].includes(comparison?.version)) return null;
  return <aside className="coding-example-scope" aria-label="반복 비교에서 확인한 신호">
    <strong>{comparison.rounds.length}회 비교에서 확인한 내 선택</strong>
    <ul>{Object.entries(comparison.summary).map(([axis, value]) => <li key={axis}>
      <strong>{CODING_CHOICES[axis].label}</strong>: {value.consistent ? `${value.answered}회 같은 선택` : value.status === 'single' ? '1회 선택 · 반복 확인 전' : value.status === 'mixed' ? '선택이 엇갈림 · 미확정' : '판단할 선택 부족 · 미확정'}
      {' '}({value.answered}/{value.total}회 응답){comparison.choices[axis] === null && (resolved ? ' · 직접 확인한 설정 적용' : ' · 최종 방식은 직접 확인 필요')}
    </li>)}</ul>
    <p>일치 횟수는 정확도나 확신 확률이 아니에요. {resolved ? '비교에서 미확정이었던 항목은 직접 확인한 설정을 따릅니다.' : '미확정 항목은 아래에서 직접 골라 주세요.'} 과제가 바뀌면 원하는 방식도 달라질 수 있어요.</p>
  </aside>;
}
