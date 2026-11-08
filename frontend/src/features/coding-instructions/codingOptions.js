export const LANGUAGES = ['Python', 'Java', 'JavaScript', 'TypeScript', 'C', 'C++', 'C#', 'Go', 'Rust', 'Kotlin', 'Swift', 'Dart', 'PHP', 'Ruby'];
export const FRAMEWORKS = {
  Python: ['FastAPI', 'Django', 'Flask'], Java: ['Spring Boot'], JavaScript: ['React', 'Vue', 'Express', 'Next.js'],
  TypeScript: ['React', 'Vue', 'Express', 'Next.js', 'NestJS'], 'C#': ['.NET', 'Unity'], 'C++': ['Qt', 'Unreal Engine'],
  Go: ['Gin', 'Echo'], Rust: ['Axum', 'Actix Web'], Kotlin: ['Spring Boot', 'Android'],
  Swift: ['SwiftUI'], Dart: ['Flutter'], PHP: ['Laravel'], Ruby: ['Rails'],
};
export function codingOptimizationKind(profile) {
  const key = `${profile.language.toLowerCase()}/${profile.framework.toLowerCase()}`;
  return { 'python/fastapi': 'fastapi', 'python/flask': 'flask', 'python/django': 'django', 'java/spring boot': 'spring_boot',
    'javascript/react': 'javascript_react', 'typescript/react': 'typescript_react',
    'javascript/vue': 'javascript_vue', 'typescript/vue': 'typescript_vue',
    'javascript/next.js': 'javascript_nextjs', 'typescript/next.js': 'typescript_nextjs',
    'typescript/nestjs': 'typescript_nestjs',
    'javascript/express': 'javascript_express', 'typescript/express': 'typescript_express' }[key] || null;
}
export const CODING_CHOICES = {
  explanation: { label: '설명 방식', options: { brief: '핵심만 간결하게', steps: '과정과 이유를 단계별로' } },
  comments: { label: '주석 정도', options: { essential: '필요한 곳에만', detailed: '핵심 로직을 자세하게' } },
  structure: { label: '코드 구성', options: { compact: '작은 작업은 간결하게', modular: '역할에 따라 나누기' } },
  output: { label: '코드 출력', options: { complete: '필요한 전체 코드', changes: '기존 코드의 변경 부분 중심' } },
};
export const DEFAULT_CODING_PROFILE = { language: 'Python', framework: '', preferences: {
  explanation: 'brief', comments: 'essential', structure: 'compact', output: 'complete',
}, extra: '' };

export async function previewCodingInstructions(profile) {
  const response = await fetch('/api/coding-instructions/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile }) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || '지침을 만들지 못했어요. 다시 시도해 주세요.');
  return data.draft;
}

export async function loadCodingExamples(profile) {
  const response = await fetch('/api/coding-instructions/examples', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile, protocol: 'repeated-v1' }) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || '코드 예시를 불러오지 못했어요. 다시 시도해 주세요.');
  return data.examples;
}
