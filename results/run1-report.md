tag=run1  answer model=claude-haiku-5-5  sessions/question=24.0

| contestant | n | errors | correct | accuracy | ingest s/q | ingest $/q | ingest tok/q | query s (median) | query $/q | context chars | $ per correct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| full-context | 60 | 0 | 53.3 | 89% | 0.0 | 0.0000 | 0 | 2.7 | 0.0100 | 250,455 | 0.0113 |
| pgvector-rag | 60 | 0 | 51.7 | 86% | 1.4 | 0.0011 | 54,309 | 2.0 | 0.0009 | 22,252 | 0.0024 |
| mem0 | 60 | 0 | 49.7 | 83% | 413.6 | 0.0669 | 530,169 | 2.3 | 0.0003 | 4,666 | 0.0812 |
| letta | 60 | 0 | 42.0 | 70% | 185.9 | 0.1384 | 1,210,407 | 3.3 | 0.0047 | 569 | 0.2044 |
| graphiti | 60 | 0 | 41.3 | 69% | 265.7 | 0.3254 | 3,078,765 | 1.9 | 0.0005 | 9,417 | 0.4731 |

| contestant | abstention | knowledge-update | multi-session | single-session-assistant | single-session-user | temporal-reasoning |
|---|---|---|---|---|---|---|
| full-context | 8.0/10 | 10.0/10 | 6.7/10 | 10.0/10 | 10.0/10 | 8.7/10 |
| pgvector-rag | 8.0/10 | 9.0/10 | 6.0/10 | 10.0/10 | 10.0/10 | 8.7/10 |
| mem0 | 8.0/10 | 10.0/10 | 6.0/10 | 8.7/10 | 10.0/10 | 7.0/10 |
| letta | 9.0/10 | 8.0/10 | 5.0/10 | 6.3/10 | 9.7/10 | 4.0/10 |
| graphiti | 8.7/10 | 6.0/10 | 6.3/10 | 5.7/10 | 6.7/10 | 8.0/10 |
