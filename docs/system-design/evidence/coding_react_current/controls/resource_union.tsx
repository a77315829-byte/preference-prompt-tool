export type Resource =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; title: string; members: string[] };
export type Props = { resource: Resource; onRetry: () => void };

export function Component({ resource, onRetry }: Props) {
  if (resource.status === 'idle') return <p role="status">Choose a project</p>;
  if (resource.status === 'loading') return <p role="status">Loading project</p>;
  if (resource.status === 'error') return <section aria-label="Project error">
    <p role="alert">{resource.message}</p><button type="button" onClick={() => onRetry()}>Retry</button>
  </section>;
  return <section aria-label="Project details">
    <h2>{resource.title}</h2>
    {resource.members.length > 0 ? <ul aria-label="Members">{resource.members.map((member, index) => <li key={`${member}-${index}`}>{member}</li>)}</ul> : <p role="status">No members</p>}
  </section>;
}
