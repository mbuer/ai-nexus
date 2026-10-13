# Feedback import schema proposal

`005_journal_feedback.sql` is an unapproved, unvalidated PostgreSQL draft.
It is intentionally outside `migrations/`: the standard migration runner must
not discover or apply it during unrelated updates.

Before promotion, validate on a disposable database: full payload shapes,
role privileges and PUBLIC revocation, target matching, concurrent revisions,
duplicate receipts and transaction/crash behavior. Review backup/recovery and
operator transport. Obtain explicit schema/import approval, then promote one
reviewed migration with code, tests and documentation in a coherent feature.
Until then, reviews remain in Utility's queue. No canonical-memory or agent
grant change is authorized by this proposal.
