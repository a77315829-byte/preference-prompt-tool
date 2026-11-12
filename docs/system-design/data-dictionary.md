# 데이터 사전

2026-11-12 · app_db.py migration 14의 빈 메모리 DB 스키마. 사용자 데이터는 포함하지 않는다.

[통합 설계서](README.md) · [추출 원자료](source-evidence.json)


## coding_optimization_jobs

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| id | TEXT | PK 1 | 없음 | — |
| owner_id | INTEGER | NOT NULL | 없음 | users.id / delete CASCADE |
| expires_at | REAL | NOT NULL | 없음 | — |
| job_json | TEXT | NOT NULL | 없음 | — |

## coding_team_guides

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| code | TEXT | PK 1 | 없음 | teams.code / delete CASCADE |
| revision | INTEGER | NOT NULL | 1 | — |
| profile_json | TEXT | NOT NULL | 없음 | — |
| rules_json | TEXT | NOT NULL | 없음 | — |

## coding_work_trials

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| id | TEXT | PK 1 | 없음 | — |
| owner_id | INTEGER | NOT NULL | 없음 | users.id / delete CASCADE |
| revision | INTEGER | NOT NULL | 1 | — |
| record_json | TEXT | NOT NULL | 없음 | — |
| updated_at | TEXT | NOT NULL | 없음 | — |

## handoff_files

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| id | TEXT | PK 1 | 없음 | — |
| handoff_id | TEXT | NOT NULL | 없음 | handoffs.id / delete CASCADE |
| name | TEXT | NOT NULL | 없음 | — |
| content_type | TEXT | NOT NULL | 없음 | — |
| size | INTEGER | NOT NULL | 없음 | — |
| data | BLOB | NOT NULL | 없음 | — |
| created_at | TEXT | NOT NULL | 없음 | — |

## handoff_versions

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| handoff_id | TEXT | PK 1 | 없음 | handoffs.id / delete CASCADE |
| revision | INTEGER | PK 2 | 없음 | — |
| actor_id | INTEGER | NULL 허용 | 없음 | users.id / delete SET NULL |
| event | TEXT | NOT NULL | 없음 | — |
| snapshot_json | TEXT | NOT NULL | 없음 | — |
| saved_at | TEXT | NOT NULL | 없음 | — |

## handoffs

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| id | TEXT | PK 1 | 없음 | — |
| owner_id | INTEGER | NOT NULL | 없음 | users.id / delete CASCADE |
| recipient_id | INTEGER | NULL 허용 | 없음 | users.id / delete SET NULL |
| recipient_from_revision | INTEGER | NOT NULL | 0 | — |
| title | TEXT | NOT NULL | 없음 | — |
| body_json | TEXT | NOT NULL | 없음 | — |
| status | TEXT | NOT NULL | 'draft' | — |
| revision | INTEGER | NOT NULL | 1 | — |
| created_at | TEXT | NOT NULL | 없음 | — |
| updated_at | TEXT | NOT NULL | 없음 | — |

## personal_prompts

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| id | TEXT | PK 1 | 없음 | — |
| owner_id | INTEGER | NOT NULL | 없음 | users.id / delete CASCADE |
| title | TEXT | NOT NULL | 없음 | — |
| domain_key | TEXT | NOT NULL | 없음 | — |
| prompt | TEXT | NOT NULL | 없음 | — |
| note | TEXT | NOT NULL | '' | — |
| revision | INTEGER | NOT NULL | 1 | — |
| created_at | TEXT | NOT NULL | 없음 | — |
| updated_at | TEXT | NOT NULL | 없음 | — |
| provenance_json | TEXT | NULL 허용 | 없음 | — |
| coding_profile_json | TEXT | NULL 허용 | 없음 | — |

## sessions

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| token_hash | TEXT | PK 1 | 없음 | — |
| user_id | INTEGER | NOT NULL | 없음 | users.id / delete CASCADE |
| created_at | TEXT | NOT NULL | 없음 | — |
| expires_at | TEXT | NOT NULL | 없음 | — |

## team_members

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| code | TEXT | PK 1 | 없음 | teams.code / delete CASCADE |
| member_key | TEXT | PK 2 | 없음 | — |
| name | TEXT | NOT NULL | 없음 | — |
| user_id | INTEGER | NULL 허용 | 없음 | users.id / delete CASCADE |
| history_json | TEXT | NOT NULL | 없음 | — |
| joined_at | TEXT | NOT NULL | 없음 | — |

## teams

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| code | TEXT | PK 1 | 없음 | — |
| domain_key | TEXT | NOT NULL | 없음 | — |
| created_by | INTEGER | NULL 허용 | 없음 | users.id / delete SET NULL |
| created_at | TEXT | NOT NULL | 없음 | — |
| name | TEXT | NOT NULL | '' | — |
| invite_until | REAL | NOT NULL | 0 | — |
| protected | INTEGER | NOT NULL | 0 | — |

## usage

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| day | TEXT | PK 1 | 없음 | — |
| kind | TEXT | PK 2 | 없음 | — |
| subject | TEXT | PK 3 | 없음 | — |
| count | INTEGER | NOT NULL | 없음 | — |

## users

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| id | INTEGER | PK 1 | 없음 | — |
| username | TEXT | NOT NULL | 없음 | — |
| password_hash | TEXT | NOT NULL | 없음 | — |
| created_at | TEXT | NOT NULL | 없음 | — |

## workspace_drafts

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| project_id | TEXT | PK 1 | 없음 | workspace_projects.id / delete CASCADE |
| user_id | INTEGER | PK 2 | 없음 | users.id / delete CASCADE |
| saved_at | TEXT | NOT NULL | 없음 | — |
| base_version | INTEGER | NOT NULL | 없음 | — |
| project_json | TEXT | NOT NULL | 없음 | — |

## workspace_members

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| project_id | TEXT | PK 1 | 없음 | workspace_projects.id / delete CASCADE |
| user_id | INTEGER | PK 2 | 없음 | users.id / delete CASCADE |
| role | TEXT | NOT NULL | 없음 | — |
| added_at | TEXT | NOT NULL | 없음 | — |

## workspace_projects

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| id | TEXT | PK 1 | 없음 | — |
| owner_id | INTEGER | NOT NULL | 없음 | users.id / delete CASCADE |
| title | TEXT | NOT NULL | 없음 | — |
| created_at | TEXT | NOT NULL | 없음 | — |
| updated_at | TEXT | NOT NULL | 없음 | — |

## workspace_versions

| 열 | 자료형 | 필수/PK | 기본값 | 참조 |
|---|---|---|---|---|
| project_id | TEXT | PK 1 | 없음 | workspace_projects.id / delete CASCADE |
| version | INTEGER | PK 2 | 없음 | — |
| saved_at | TEXT | NOT NULL | 없음 | — |
| label | TEXT | NOT NULL | 없음 | — |
| project_json | TEXT | NOT NULL | 없음 | — |

JSON 열의 내부 필드와 출처 참조는 DB 외래키가 아니다. SQLite의 기본값·NULL·복합키 의미는 위 원자료와 애플리케이션 검증을 함께 확인한다.
