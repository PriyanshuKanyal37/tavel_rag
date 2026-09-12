-- Travel Inn RAG schema. Postgres 18 + pgvector 0.8.6 + pg_trgm 1.6 on Neon.
-- Safe to re-run: everything is "if not exists" except the explicit reset below.

create extension if not exists vector;
create extension if not exists pg_trgm;

create table if not exists documents (
  sha1          text primary key,          -- content hash; also the R2 filename
  rel_path      text not null,             -- client's own folder taxonomy
  ext           text,
  page_count    int,                       -- pages (PDF) or tiles (image)
  is_tiled      boolean not null default false,
  transcription text not null,             -- what the vision model read
  text_layer    text,                      -- PDF text layer, or OCR for images
  ocr_engine    text,
  extractor     text,                      -- model id that read it
  embedding     vector(1536),
  superseded_by text references documents(sha1),
  created_at    timestamptz default now()
);

-- entity_type is FREE TEXT on purpose. An enum of travel words (hotel, park,
-- airport...) would decide today what kinds of thing can exist in a corpus we
-- have not seen yet. The reader proposes a type; unknown ones are governed the
-- same way labels are -- reviewed and promoted, never silently dropped.
create table if not exists entities (
  id             bigserial primary key,
  entity_type    text not null,
  canonical_name text not null,
  aliases        text[] not null default '{}',
  state          text,
  city           text,
  facts          jsonb not null default '{}'
);
create index if not exists entities_facts_idx on entities using gin (facts jsonb_path_ops);
create index if not exists entities_name_trgm on entities using gin (canonical_name gin_trgm_ops);
create index if not exists entities_type_idx on entities (entity_type);
create index if not exists entities_state_idx on entities (state);

create table if not exists entity_documents (
  entity_id  bigint references entities(id) on delete cascade,
  sha1       text   references documents(sha1) on delete cascade,
  primary key (entity_id, sha1)
);

-- THE VOCABULARY IS DATA, NOT CODE.
--
-- Everything the pipeline knows about a domain lives in this table: which
-- labels exist, what shape their values take, whether one entity may hold many
-- of them, and whether a label names another entity. The extraction prompt is
-- BUILT from these rows and the validation rules are DRIVEN by them, so
-- teaching the system a new kind of data is an INSERT -- never a code change,
-- a prompt rewrite or a migration.
create table if not exists attribute_vocabulary (
  key            text primary key,
  definition     text,        -- one line. A label without one attracts wrong values.
  not_this       text,        -- the confusable thing it must NOT capture
  value_type     text,        -- number | money | quantity | date | boolean | text | list
  unit_kind      text,        -- distance | duration | area | currency | count | none
  cardinality    text default 'multi',   -- 'scalar' = one per entity; 'multi' = many
  relation_kind  text,        -- non-null => the value NAMES another entity; makes an edge
  status         text default 'proposed',-- approved | proposed | alias
  alias_of       text,        -- status 'alias' => facts under this key are rewritten to alias_of
  proposed_count int default 0,          -- how many times readers asked for it
  created_at     timestamptz default now()
);
create index if not exists vocab_alias_idx on attribute_vocabulary (alias_of) where alias_of is not null;
create index if not exists vocab_status_idx on attribute_vocabulary (status);

create table if not exists fact_evidence (
  id            bigserial primary key,
  entity_id     bigint references entities(id) on delete cascade,
  key           text not null,
  scope         jsonb,                     -- {"category":"Deluxe Room"} -- NOT a conflict with the unscoped fact
  value_text    text,
  value_num     numeric,
  value_unit    text,
  value_currency text,
  asserted_as   text not null default 'stated',   -- stated | negated | hedged
  evidence      text,
  evidence_type text not null default 'text',     -- text | visual
  page          int,                       -- page number, or tile index
  bbox          jsonb,                     -- [x0,y0,x1,y1] on the page image, when known
  sha1          text references documents(sha1) on delete cascade,
  section       text,
  block_kind    text,
  confidence    text,
  rank          text not null default 'normal'    -- preferred | normal | deprecated
);
create index if not exists fact_live_idx on fact_evidence (entity_id, key) where rank <> 'deprecated';
create index if not exists fact_key_idx on fact_evidence (key);
create index if not exists fact_sha_idx on fact_evidence (sha1);

-- Relationships between entities. `kind` is free text and `props` holds
-- whatever that relationship carries -- distance and duration for a spatial
-- link today, but a contract term, an ownership share or a validity window
-- just as easily. Nothing here assumes the relation is about travel.
create table if not exists connections (
  id          bigserial primary key,
  from_entity bigint references entities(id) on delete cascade,
  to_entity   bigint references entities(id) on delete cascade,
  kind        text not null,               -- nearest_airport | operated_by | supersedes | ...
  props       jsonb not null default '{}', -- {"distance_km": 97, "duration_h": 2.5}
  sha1        text references documents(sha1) on delete cascade,
  evidence    text
);
create index if not exists conn_props_idx on connections using gin (props jsonb_path_ops);
create index if not exists conn_from_idx on connections (from_entity, kind);
create index if not exists conn_to_idx on connections (to_entity, kind);

create table if not exists review_queue (
  id         bigserial primary key,
  reason     text,
  entity     text,
  key        text,
  detail     jsonb,
  sha1       text,
  resolved   boolean not null default false,
  created_at timestamptz default now()
);
create index if not exists review_open_idx on review_queue (reason) where not resolved;

-- ============================================================
-- THE ANSWERING SIDE: who can sign in, and what was asked.
-- Everything above this line is ingestion and is never written at query time.
-- ============================================================

-- Exactly ONE account, shared by everyone at Travel Inn. The check constraint
-- makes a second account impossible, so "one shared login" is enforced by the
-- database rather than trusted to the code. If individual accounts are ever
-- wanted, dropping the constraint is the entire change.
create table if not exists app_account (
  id            smallint primary key default 1,
  email         text not null unique,
  password_hash text not null,            -- bcrypt; never readable
  name          text not null,
  active        boolean not null default true,
  created_at    timestamptz default now(),
  constraint one_account check (id = 1)
);

-- One row per signed-in BROWSER. The login cookie carries this id, signed.
--
-- A stateless signed cookie cannot be revoked. Clearing it removes it from the
-- browser that asked, while any copy already taken stays valid until it expires
-- -- so "log out" would not actually end a session. A version counter on
-- app_account cannot fix it either: there is exactly ONE account row, so
-- bumping it signs every browser out at once. Per-browser rows are the only
-- shape where both promises hold -- one browser logs out, the others stay in,
-- and a stolen cookie stops working the moment its row is revoked.
--
-- That matters MORE with a shared password, not less: it is the only way to cut
-- off one leaked login without changing the credentials the whole team uses.
create table if not exists login_session (
  id         uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  last_seen  timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz,             -- set by logout. Non-null => rejected.
  user_agent text
);
create index if not exists login_session_live_idx
  on login_session (expires_at) where revoked_at is null;

-- A conversation thread. Shared: anyone signed in may open or continue any of
-- them. The working set lives HERE, not on a login session -- a browser being
-- signed in and a thread of questions have different lifetimes.
--
-- CONCURRENCY: working_set is read, merged and written back whole. Two browsers
-- asking in the same thread at once would both read the old array and the second
-- write would erase the first one's documents -- silently, with no constraint to
-- catch it. Every writer must take `select … from conversation where id = %s
-- for update` in the SAME transaction that writes the turn.
create table if not exists conversation (
  id           bigserial primary key,
  title        text,                      -- taken from the first question
  working_set  jsonb not null default '[]',
     -- [{"sha1":"…","level":"full|facts|summary","turn_added":3}]
  summary      text,                      -- older turns, compressed
  tokens_est   int  not null default 0,   -- drives the degrade ladder
  created_at   timestamptz default now(),
  last_active  timestamptz default now()
);
create index if not exists conversation_recent_idx on conversation (last_active desc);

-- Every message, question and answer alike, with what it cost.
create table if not exists turn (
  id              bigserial primary key,
  conversation_id bigint not null references conversation(id) on delete cascade,
  seq             int    not null,        -- 1,2,3… within the thread
  role            text   not null,        -- 'user' | 'assistant' (message type, not access)
  text            text   not null,
  -- an answer that was cut off is not an answer. Without this column a
  -- half-streamed reply is indistinguishable from a complete one on reload.
  status          text   not null default 'complete',
                  -- streaming | complete | cut | interrupted | failed
                  -- 'cut' = the model ran out of output room mid-sentence
  plan            jsonb,                  -- what the planner extracted
  sources         jsonb,                  -- [{"n":1,"sha1":"…","page":2}]
  cost_inr        numeric,
  ms              int,
  created_at      timestamptz default now(),
  -- two people answering in the same thread at once would both write turn 7.
  -- The database REFUSES the second; the writer must then retry at seq+1.
  -- This orders writes. It does not serialise them: see conversation above.
  unique (conversation_id, seq)
);
create index if not exists turn_thread_idx on turn (conversation_id, seq);
-- for databases created before `status` existed
alter table turn add column if not exists status text not null default 'complete';

-- HOW A THREAD GETS ITS NAME. Four states, and it only ever moves forward:
--
--   first    the title is the opening message, whatever it was. "hi" included.
--   seeded   the title is the first question that actually needed the corpus.
--   settled  a model read the first two real questions and wrote a short name.
--   manual   a person typed it. Nothing automatic may ever overwrite this.
--
-- Small talk does not advance the state, so a thread of pleasantries keeps its
-- pleasantry of a name and never burns a model call. Once past `seeded` the
-- name is frozen: a title that keeps changing is a thread you cannot find again.
alter table conversation add column if not exists title_state text not null
  default 'first';

-- Searching titles alone cannot find the thread where the ANSWER mentioned a
-- pool. These indexes are what let the search read the messages themselves.
--
-- TWO of them, because one cannot do both jobs. `english` stems, so "property"
-- finds "properties" -- but "swimming" is stored as "swim", and someone typing
-- their way to it hits nothing at "swimm". `simple` stores the word whole, so
-- prefixes match as you type but "property" no longer finds "properties".
-- Measured, not assumed: each config fails a case the other passes, and
-- searching both vectors passes all of them.
create index if not exists turn_text_fts_idx on turn
  using gin (to_tsvector('english', text));
create index if not exists turn_text_simple_idx on turn
  using gin (to_tsvector('simple', text));

-- Festival dates and park closure windows. A one-time data load, not extraction.
--
-- A date is a fact about ONE year. Holi moves every Gregorian year and closure
-- windows are reset annually, so "festival dates never change" was wrong: every
-- row carries the source it came from and the day someone last checked it.
create table if not exists calendar_event (
  id          bigserial primary key,
  kind        text not null,        -- festival | park_closure | seasonal
  name        text not null,        -- 'Holi' | 'Monsoon closure'
  starts_on   date not null,
  ends_on     date,
  entity_id   bigint references entities(id) on delete cascade,  -- null = nationwide
  note        text,
  source_url  text,                 -- where it came from. Null means unverified.
  verified_on date,
  created_at  timestamptz default now(),
  unique (kind, name, starts_on, entity_id)
);
create index if not exists calendar_name_idx on calendar_event (name);
create index if not exists calendar_when_idx on calendar_event (starts_on);

-- NO domain-specific promoted columns here, deliberately.
--
-- An earlier version carried `room_count` as a generated column, to demonstrate
-- that a JSONB key can become a real indexed column with no table rewrite. The
-- pattern is sound; hard-coding a HOTEL field into a schema that must accept
-- data we have not seen is not. Promote a label only when measured query load
-- justifies it, with:
--
--   alter table entities add column <label> <type>
--     generated always as (nullif(facts->>'<label>','')::<type>) stored;
--   create index on entities (<label>) where <label> is not null;
--
-- Until then the GIN index on `facts` below serves every key equally, and no
-- key is privileged by a guess made in advance.

-- User workspace actions. These are shared because v1 has one shared account.
create table if not exists saved_answer (
  answer_id   text primary key,
  text        text not null,
  session_id  bigint references conversation(id) on delete set null,
  created_at  timestamptz not null default now()
);
create index if not exists saved_answer_recent_idx on saved_answer (created_at desc);

create table if not exists answer_feedback (
  answer_id   text primary key,
  kind        text not null check (kind in ('helpful', 'correction')),
  -- What the salesperson actually said is the point of the record; `kind` alone
  -- only says that something was wrong, never what.
  reason      text,               -- wrong_fact | missing | wrong_source | outdated | other
  note        text,               -- free text, in their words
  created_at  timestamptz not null default now()
);
alter table answer_feedback add column if not exists reason text;
alter table answer_feedback add column if not exists note   text;

create table if not exists saved_source (
  sha1       text primary key references documents(sha1) on delete cascade,
  created_at timestamptz not null default now()
);
