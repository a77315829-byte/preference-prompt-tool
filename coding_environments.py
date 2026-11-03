"""Explicit GEPA environment registry; unlisted pairs remain unsupported."""
ENVIRONMENTS = {
    'fastapi': ('Python', 'FastAPI', 'api'),
    'flask': ('Python', 'Flask', 'flask'),
    'django': ('Python', 'Django', 'django'),
    'spring_boot': ('Java', 'Spring Boot', 'api'),
    'javascript_react': ('JavaScript', 'React', 'react'),
    'typescript_react': ('TypeScript', 'React', 'react'),
    'javascript_express': ('JavaScript', 'Express', 'express'),
    'typescript_express': ('TypeScript', 'Express', 'express'),
    'javascript_vue': ('JavaScript', 'Vue', 'vue'),
    'typescript_vue': ('TypeScript', 'Vue', 'vue'),
    'javascript_nextjs': ('JavaScript', 'Next.js', 'nextjs'),
    'typescript_nextjs': ('TypeScript', 'Next.js', 'nextjs'),
    'typescript_nestjs': ('TypeScript', 'NestJS', 'nestjs'),
}


def environment_kind(profile):
    pair = (profile['language'].casefold(), profile['framework'].casefold())
    return next((key for key, (language, framework, _) in ENVIRONMENTS.items()
                 if pair == (language.casefold(), framework.casefold())), None)
