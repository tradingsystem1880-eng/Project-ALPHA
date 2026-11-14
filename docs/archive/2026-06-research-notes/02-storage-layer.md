# Project ALPHA — Research 02: Time-Series Storage Layer

**Mission:** Recommend the best FREE / open-source storage for historical tick data + OHLCV bars + corporate-actions, for a SOLO researcher on ONE machine.
**Date:** 2026-06-14
**Constraints recap:** $0/free, self-hosted, Python-first, single user / single machine, backtesting + statistical validation + paper trading, institutional-grade methodology operated solo. kdb+ is OUT (paid).

---

## TL;DR — The Verdict

**Recommended stack: Parquet-on-disk (the source of truth) + DuckDB (the query/compute engine) + Polars (DataFrame manipulation), all glued by Apache Arrow.** Optionally promote to **DuckLake** (DuckDB's SQL-catalog lakehouse format, v1.0 production-ready as of April 2026) once you want ACID snapshots, time-travel, and clean incremental appends without hand-managing files.

- **ClickHouse for a solo, free, single-machine setup is OVERKILL.** It is a client-server cluster database; you'd be running, tuning, and babysitting a server (MergeTree config, background merges, backups, monitoring) to get performance that is *within ~1.3–2.6x* of DuckDB on single-node analytical queries — queries DuckDB runs in-process with **zero servers and zero ops**. The operational tax buys you nothing a solo researcher needs. ([oneuptime](https://oneuptime.com/blog/post/2026-03-31-clickhouse-vs-duckdb-analytical-workloads/view), [tinybird](https://www.tinybird.co/blog/clickhouse-vs-duckdb-nodes))
- **A database is NOT needed.** Parquet + DuckDB/Polars is enough for a single-machine quant workflow well into the multi-hundred-GB / low-TB range, because DuckDB does out-of-core (spill-to-disk) execution. ([DuckDB memory mgmt](https://duckdb.org/2024/07/09/memory-management))
- **ArcticDB is tempting but disqualified on the "$0/free" constraint** due to its Business Source License. Its own docs say a commercial agreement is required for use "where any economic benefit is being derived." A quant trading platform exists precisely to derive economic benefit — that is a legal grey zone you should not build a foundation on for free. (Details in §3.5.) ([ArcticDB licensing FAQ](https://docs.arcticdb.io/latest/licensing/), [LICENSE.txt](https://github.com/man-group/ArcticDB/blob/master/LICENSE.txt))
- **Corporate actions:** store a **separate, point-in-time (bitemporal) corporate-actions table**, keep prices **RAW (unadjusted)**, and apply splits/dividends **on-the-fly at query time** via a cumulative adjustment factor joined with DuckDB's **`ASOF JOIN`**. This is the only way to guarantee no look-ahead bias. (Full recipe in §6.)

---

## 1. Decision criteria (what actually matters for a solo quant on one box)

| Criterion | Why it matters here |
|---|---|
| **Ops burden for ONE person** | You are the DBA, SRE, and researcher. Every running server is a thing that breaks at 2am. **Embedded > server.** |
| **Columnar scan speed (range queries)** | Backtests are "give me symbol X, bars between date A and B, all columns" → columnar + predicate/partition pruning. |
| **Ingestion throughput** | You bulk-load historical dumps occasionally + append daily. You are NOT ingesting a live exchange firehose. Batch write speed > streaming write speed. |
| **On-disk compression** | Tick data is large. Good compression = more history on a laptop SSD. |
| **Python ergonomics** | Python-first. Zero-copy to Pandas/Polars/Arrow is a feature, not a nicety. |
| **Partitioning (symbol / date)** | Determines query speed and how cleanly you append/correct data. |
| **Point-in-time corporate actions** | Institutional-grade = no look-ahead. The storage layer must support as-of joins and bitemporal modeling. |
| **License = truly free** | Hard $0 constraint. BSL/source-available with production restrictions ≠ free for this use. |

---

## 2. Candidate scorecard (single-machine, solo, free)

Scale: ✅ strong / 🟡 adequate / ❌ weak-or-disqualifying. Weighted for THIS use case.

| | Ops burden (server?) | Scan speed (single node) | Batch ingest | Compression | Python UX | Partitioning | Point-in-time / CA modeling | Truly free? | **Fit** |
|---|---|---|---|---|---|---|---|---|---|
| **DuckDB + Parquet + Polars** | ✅ **No server**, in-process | ✅ Top-tier single-node | 🟡 Single-writer; fast bulk COPY | ✅ Parquet+ZSTD ~10–14x | ✅ Best-in-class (Arrow zero-copy) | ✅ Hive (symbol/date) | ✅ Native `ASOF JOIN` + window fns | ✅ MIT | ★ **Winner** |
| **Plain Parquet + Polars/pandas** | ✅ No server, just files | 🟡 Good (no global indexes) | 🟡 Manual file mgmt | ✅ Same Parquet | ✅ Excellent | ✅ Hive dirs | 🟡 Possible but you hand-roll joins | ✅ Apache-2.0 / MIT | ★ **Co-winner / substrate** |
| **DuckLake (DuckDB lakehouse)** | ✅ Embedded; SQLite/DuckDB catalog | ✅ DuckDB engine | ✅ ACID appends, snapshots | ✅ Parquet | ✅ DuckDB/Polars | ✅ Built-in | ✅ Snapshots = time travel | ✅ MIT | ★ **Upgrade path** |
| **ArcticDB** | ✅ Embedded (no server) | ✅ Fast columnar | ✅ Strong appends | ✅ Good | ✅ Pandas-native, versioned | 🟡 By symbol; opaque format | ✅ Bitemporal/versioned (great) | ❌ **BSL — not free for econ-benefit use** | ❌ **Disqualified on license** |
| **ClickHouse (OSS)** | ❌ **Server + merges + tuning** | ✅ Excellent | ✅ Very high | ✅ Excellent (~10:1) | 🟡 clickhouse-connect | ✅ Partition+ORDER BY | 🟡 Doable in SQL, no native asof-join ergonomics like DuckDB | ✅ Apache-2.0 | 🟡 **Overkill** |
| **QuestDB (OSS)** | ❌ Server (JVM) | ✅ Fast for time queries | ✅✅ **Best streaming ingest** | 🟡 Good | 🟡 SQL/ILP | 🟡 By time partitions | 🟡 SQL `ASOF JOIN` exists; CA modeling manual | 🟡 Apache-2.0 core | 🟡 Built for live firehose you don't have |
| **TimescaleDB (OSS)** | ❌ **Full Postgres server** | 🟡 Row-ish; columnar via compression | 🟡 6–13x slower ingest than QuestDB | 🟡 Decent compressed | 🟡 psycopg/SQL | 🟡 Hypertable chunks | ✅ Postgres = rich SQL for PIT | 🟡 Apache-2.0 (TSL features restricted) | 🟡 Server tax, weaker columnar scans |

Sources for the comparative claims are cited inline throughout §3 and §4.

---

## 3. Per-engine deep dive

### 3.1 DuckDB (+ Parquet + Polars) — **the recommendation**

**What it is:** An embedded, in-process OLAP database (the "SQLite for analytics"). No server, no daemon — it's a Python `pip install duckdb` and it runs inside your process. ([DuckDB docs](https://duckdb.org/docs/current/data/parquet/overview))

**Ops burden:** Effectively zero. "DuckDB runs embedded in your application on a single machine with zero operational overhead." Nothing to start, monitor, or back up beyond your files. ([dench.com](https://www.dench.com/blog/duckdb-vs-clickhouse))

**Scan speed:** On single-node analytical benchmarks (ClickBench, TPC-H SF10/100, 1.1B-row NYC taxi), DuckDB is in the same league as ClickHouse and far ahead of row stores. Representative numbers:
- ClickBench relative runtime (lower=better): ClickHouse ×1.75, **DuckDB ×2.19**, QuestDB ×2.62. ([timestored](https://www.timestored.com/data/time-series-database-benchmarks))
- 1.1B NYC taxi total query time (normalized to kdb+ = 1.0): ClickHouse 2.3, **DuckDB 2.8** — i.e., DuckDB is ~0.8x of ClickHouse on the same desktop CPU. ([timestored](https://www.timestored.com/data/time-series-database-benchmarks))
- For datasets under ~10GB, DuckDB frequently *beats* ClickHouse because it avoids network/distributed/coordination overhead. ([oneuptime](https://oneuptime.com/blog/post/2026-03-31-clickhouse-vs-duckdb-analytical-workloads/view))

**Larger-than-memory:** DuckDB supports out-of-core execution — it spills grouping/joining/sorting/windowing to disk, so you can query datasets larger than RAM. Caveats: some aggregates (`list()`, `string_agg()`) and stacked blocking operators can still OOM; pure in-memory mode (`:memory:`) cannot spill. For a laptop this means: point it at a persistent DB file or run over Parquet on disk, and you can churn through data many times your RAM. ([DuckDB memory mgmt](https://duckdb.org/2024/07/09/memory-management), [tuning](https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads))

**Ingest / writes:** Bulk `COPY ... TO` is fast and the normal path for loading historical dumps and appending daily bars. **Limitation: single writer.** "DuckDB isn't built to handle concurrent writes — it only allows one writer at a time," and it isn't designed for many tiny concurrent queries. For a solo researcher this is a non-issue (one ETL job appends; backtests are read-only and can open the file read-only / use separate connections). ([dev.to](https://dev.to/prithwish_nath/the-practical-limits-of-duckdb-on-commodity-hardware-f76))

**Compression:** Via Parquet output. ZSTD gives ~14.3x vs ~8.7x for Snappy on typical data; CSV→Parquet conversions routinely cut footprint ~70–95%. DuckDB also has its own lightweight columnar compression in its native file format. ([DuckDB lightweight compression](https://duckdb.org/2022/10/28/lightweight-compression), [file formats](https://duckdb.org/docs/current/guides/performance/file_formats))

**Python UX / Arrow:** This is DuckDB's superpower for a backtester. DuckDB speaks Arrow natively — it can query Polars/Pandas DataFrames in place and return results as Arrow with **near-zero-copy** (shared Arrow buffers). It also added Arrow IPC support in 2025. You can mix SQL and Polars freely without serialization tax. ([DuckDB Arrow IPC](https://duckdb.org/2025/05/23/arrow-ipc-support-in-duckdb), [zero-copy](https://medium.com/@ThinkingLoop/duckdb-polars-zero-copy-joins-that-fly-30203084ade8))

**Partitioning:** Native Hive partitioning on write (`COPY ... (FORMAT PARQUET, PARTITION_BY (...))`) and read (`read_parquet(..., hive_partitioning=true, hive_types={...})`). Lets you partition by symbol and/or date and prune at query time. ([DuckDB Hive partitioning](https://duckdb.org/docs/lts/data/partitioning/hive_partitioning))

**Corporate actions:** Native **`ASOF JOIN`** (fuzzy temporal "most-recent-preceding" join) + window functions make on-the-fly, bias-free adjustment a one-query operation. This is the single biggest reason DuckDB beats plain Parquet for *this* domain. (See §6.) ([DuckDB ASOF](https://duckdb.org/2023/09/15/asof-joins-fuzzy-temporal-lookups))

**Weaknesses:** single-writer (fine solo); no built-in multi-version time-travel on its own (use DuckLake or git-style Parquet snapshots if you need it); not for high-concurrency multi-user serving (irrelevant here).

---

### 3.2 Plain Parquet + Polars/pandas — **the substrate, and a valid minimal answer**

**What it is:** Just files. Parquet is the columnar on-disk format; Polars (Rust, Arrow-native, multithreaded, lazy) or pandas reads them.

- **Pros:** Zero infrastructure, maximum portability, Parquet is the lingua franca every tool reads. Polars+DuckDB have been stress-tested on **2 TB** of Parquet (single 140GB files and many-small-files) on commodity hardware. Polars' lazy engine + predicate/projection pushdown means you only read the columns/row-groups you need. ([codecentric](https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-polars-performance-and-memory-with-massive-parquet-data))
- **Cons vs DuckDB:** no SQL engine, no global statistics/indexes beyond Parquet row-group min/max, and you hand-roll temporal joins (as-of logic) yourself. Multi-file appends/corrections become a manual file-management chore.

**Verdict:** Use Parquet as your **source-of-truth on disk regardless**, and put DuckDB on top of it. Polars handles in-memory feature engineering and per-symbol vectorized ops; DuckDB handles cross-file SQL, range scans, and as-of joins. They share Arrow, so moving between them is ~free.

**When does Parquet-only stop being enough?** See §7.

---

### 3.3 DuckLake — **the clean upgrade path**

**What it is:** An open lakehouse format from the DuckDB team (v0.1 May 2025, **v1.0 production-ready April 2026**). Two parts: Parquet files for data + a small SQL **catalog database** (SQLite, DuckDB, or Postgres) for metadata. Adds snapshots, **time-travel queries**, schema evolution, partitioning, and **ACID transactions over multi-table operations** — fixing the "many small changes/appends" pain of raw Parquet. ([ducklake.select](https://ducklake.select/), [v1.0 announcement](https://ducklake.select/2026/04/13/ducklake-10/), [theregister](https://www.theregister.com/2026/04/16/duckdb_uses_rdbms_lakehouse/))

**Why it matters here:** Daily appends + occasional historical corrections (vendor restatements of splits/dividends) are exactly what a quant data lake does. DuckLake gives you transactional appends and snapshot-based time-travel **without** giving up the embedded, server-free model — the catalog can just be a local SQLite/DuckDB file. It is the natural answer to "I want ArcticDB-style versioning but actually free and SQL-native."

**Recommendation:** Start on plain Hive-partitioned Parquet + DuckDB (simplest). Migrate the managed tables (bars, corporate actions) to DuckLake once you want transactional appends + time-travel. Keep raw immutable tick dumps as plain Parquet.

---

### 3.4 ClickHouse (self-hosted OSS) — **OVERKILL for this use (Key Question #1)**

**What it is:** A best-in-class columnar OLAP database — but a **client-server** system built for many concurrent users and horizontally-scaled, petabyte, high-concurrency workloads. Apache-2.0 licensed (genuinely free). ([cloudraft](https://www.cloudraft.io/blog/clickhouse-vs-duckdb))

**The ops reality for ONE person:** "ClickHouse requires server management, schema design for its MergeTree engine, shard planning, and backup configuration… self-hosting and tuning is a real engineering commitment." You run a server process, manage background merges and parts, configure memory, set up backups, and monitor it — forever. ([dench.com](https://www.dench.com/blog/duckdb-vs-clickhouse), [oneuptime](https://oneuptime.com/blog/post/2026-03-31-clickhouse-vs-duckdb-analytical-workloads/view))

**What that buys you over DuckDB on one machine:** very little. On single-node analytical queries ClickHouse is ~1.3x–2.6x faster than DuckDB in some benchmarks and *slower* than DuckDB on sub-10GB workloads. Tinybird's own analysis frames it as "how many nodes do you need?" — ClickHouse's advantages are about *scale-out and concurrency*, neither of which a solo researcher has. ([tinybird](https://www.tinybird.co/blog/clickhouse-vs-duckdb-nodes), [oneuptime](https://oneuptime.com/blog/post/2026-03-31-clickhouse-vs-duckdb-analytical-workloads/view))

**Verdict on the original blueprint:** The blueprint's ClickHouse recommendation is appropriate for a *team/firm with a shared, always-on, multi-TB analytics service*. For a **single user on one laptop with $0 budget**, it is the wrong tool: you pay a permanent operational tax (a running, tunable, backup-needing server) for performance parity-to-modest-gains over an embedded engine that needs none of it. **Use DuckDB.** Revisit ClickHouse only if ALPHA ever becomes multi-user / always-on / needs a shared real-time serving layer.

---

### 3.5 ArcticDB (Man Group, "OSS") — **technically excellent, DISQUALIFIED on the free constraint**

**What it is:** A serverless, embedded DataFrame database purpose-built for the Python quant stack by Man Group (with Bloomberg). No server; installs as a pip package; backends include local disk (LMDB), in-memory, and S3-compatible (MinIO/Ceph/etc.). It is genuinely designed for *exactly this domain* — "20-year history of 400,000+ securities in a single symbol," deep tick history, bitemporal versioning with "time travel," daily appends, and historical corrections with automatic deduplication of unchanged data. For point-in-time corporate-action modeling this is arguably the most purpose-built option on the list. ([GitHub](https://github.com/man-group/ArcticDB), [docs FAQ](https://docs.arcticdb.io/4.5.0/faq/), [arcticdb.io](https://arcticdb.io/))

**Why it's disqualified for Project ALPHA:** The license. ArcticDB is **Business Source License 1.1**, which is *source-available, not open-source*, reverting to Apache-2.0 only two years after each version's release. The Additional Use Grant permits "non-production use" and forbids offering it as a "Database Service." That alone might sound OK for a solo user — **but ArcticDB's own licensing page goes further**, stating a commercial agreement is required for "any business use… including use in research or dev environments, or **where any economic benefit is being derived**." ([licensing FAQ](https://docs.arcticdb.io/latest/licensing/), [LICENSE.txt](https://github.com/man-group/ArcticDB/blob/master/LICENSE.txt), [BSL explainer](https://www.tldrlegal.com/license/business-source-license-bsl-1-1))

A personal quant trading research platform whose explicit purpose is to find and trade profitable strategies is, by construction, deriving (or intending to derive) economic benefit. The official docs are internally inconsistent (one page says "free for non-commercial, personal, or academic use"; another says any economic-benefit use needs a commercial license), and **building your data foundation on that ambiguity violates the hard "$0/free, open-source only" constraint.** If you ever wanted to use it, you'd need written clarification from Man Group. Net: **excellent tech, wrong license for this project.** (If the license were Apache-2.0, ArcticDB would be a serious contender alongside DuckDB.)

> Practical note: DuckLake gives you ~80% of what made ArcticDB attractive here (embedded, versioned/time-travel, append/correct, S3-or-local) under a clean MIT/Apache license. That's the free substitute.

---

### 3.6 QuestDB (OSS) — **built for a firehose you don't have**

**What it is:** A time-series database (Java/JVM) optimized for *high-throughput streaming ingestion* and low-latency time queries; popular in capital markets for live tick capture. Apache-2.0 core. Runs as a **server** (or Docker). ([questdb](https://questdb.com/blog/clickhouse-vs-questdb-comparison/))

- **Strength:** Ingestion. ~4M rows/sec on modest hardware; 6–13x faster ingest than TimescaleDB; native InfluxDB Line Protocol. It even stores historical data as Parquet now and supports SQL `ASOF JOIN`. ([questdb vs timescale](https://questdb.com/blog/timescaledb-vs-questdb-comparison/), [questdb tick 2025](https://www.timestored.com/data/questdb-for-tick-data-2025))
- **Why it's not the pick:** Your workload is *batch historical loads + daily appends + read-heavy backtests*, not a live exchange feed. You'd run and maintain a JVM server to get an ingestion superpower you won't use, while its single-node analytical scan ranking (ClickBench ×2.62) trails DuckDB (×2.19). The server tax isn't justified. ([timestored](https://www.timestored.com/data/time-series-database-benchmarks))
- **When QuestDB would make sense:** if/when paper-trading evolves into capturing your own live L1/L2 tick stream in real time at high rates. At that point QuestDB-for-live-capture + Parquet-export-to-DuckDB-for-research is a clean split.

---

### 3.7 TimescaleDB (OSS) — **Postgres tax, weaker columnar scans**

**What it is:** A PostgreSQL *extension* that adds time-series features (hypertables, chunking, columnar compression). It "inherently requires a PostgreSQL server to run." Core is Apache-2.0; some features sit under the restrictive Timescale License (TSL). ([db-engines](https://db-engines.com/de/system/PostgreSQL%3BQuestDB%3BTimescaleDB))

- **Strength:** Full Postgres SQL, ACID, mature tooling — genuinely nice for rich point-in-time relational modeling, and if you already run Postgres elsewhere it's low marginal cost.
- **Why it's not the pick:** It's fundamentally a row-store with columnar compression bolted on, so analytical *scan* throughput trails the true columnar engines; ingest is 6–13x slower than QuestDB; and you must run/maintain a Postgres server. For "scan a column range across millions of bars," DuckDB-on-Parquet is simpler and faster. ([questdb vs timescale](https://questdb.com/blog/timescaledb-vs-questdb-comparison/))

---

## 4. Compression & disk-footprint expectations

- **Parquet + ZSTD** is the right default: ~**14x** typical compression vs ~8.7x for Snappy; CSV→Parquet conversions commonly land **70–95% smaller**. Tune `COMPRESSION ZSTD` and `COMPRESSION_LEVEL` (3–9; higher = smaller, slower writes). ([DuckDB lightweight compression](https://duckdb.org/2022/10/28/lightweight-compression), [DuckDB parquet encodings](https://duckdb.org/2025/01/22/parquet-encodings))
- ClickHouse advertises ~10:1; in practice columnar + ZSTD across all these engines lands in the same order of magnitude, so **compression is not a differentiator** — they all compress well. The differentiator is ops + Python ergonomics + as-of join support. ([cloudraft](https://www.cloudraft.io/blog/clickhouse-vs-duckdb))
- **Skepticism note:** vendor ingestion/compression benchmarks are self-serving ("each vendor's benchmark showed itself fastest at ingestion" — timestored). The KX/kdb+ TSBS post claiming competitors are "1100x slower" is KX marketing its own paid product and should be heavily discounted; the *neutral* cross-benchmarks (ClickBench, timestored aggregation) put DuckDB/ClickHouse/QuestDB within ~1.5x of each other on single-node analytics. ([timestored](https://www.timestored.com/data/time-series-database-benchmarks), [KX TSBS (treat skeptically)](https://kx.com/blog/benchmarking-kdb-x-vs-questdb-clickhouse-timescaledb-and-influxdb-with-tsbs/))

---

## 5. Schema + partitioning design (Key Question #2)

Layout the data lake as immutable raw + managed derived tables. Directory sketch:

```
data/
  raw/                         # immutable vendor dumps (never edited)
  trades/                      # tick/trade data  (Parquet, Hive-partitioned)
    symbol=AAPL/date=2025-01-02/part.parquet
  quotes/                      # L1 quotes (optional, same scheme)
    symbol=AAPL/date=2025-01-02/part.parquet
  bars/                        # OHLCV, partitioned by timeframe then date
    tf=1m/date=2025-01-02/part.parquet
    tf=1d/year=2025/part.parquet
  corporate_actions/           # small; single table (or DuckLake table)
    corporate_actions.parquet
  reference/                   # symbology / security master (point-in-time)
    security_master.parquet
```

### (a) Tick / trade data
Partition by **`symbol` then `date`** (`symbol=.../date=YYYY-MM-DD/`). Backtests almost always filter by *one or few symbols over a date range* → symbol-first pruning reads only the relevant directories; date sub-partitions keep individual files in the tens-of-MB sweet spot and make daily appends trivial (write one new `date=` folder).

```sql
-- trades schema (columns)
ts            TIMESTAMP   -- event time, UTC, microsecond
symbol        VARCHAR     -- (also the partition key)
price         DOUBLE
size          INTEGER     -- or BIGINT
exchange      VARCHAR
conditions    VARCHAR     -- trade condition codes
-- partition cols materialized in path: symbol, date
```
Sort rows by `ts` within each file so Parquet row-group min/max stats enable time-range skipping. Watch the **small-files problem**: don't partition so finely you get millions of tiny files — for thin/illiquid names, `symbol=.../year=YYYY/` may be better than per-day. DuckDB warns partitioning helps only if keys aren't badly skewed. ([DuckDB Hive partitioning](https://duckdb.org/docs/lts/data/partitioning/hive_partitioning), [motherduck partitioned writes](https://motherduck.com/learn/partitioned-writes-parquet-ducklake/))

### (b) OHLCV bars at multiple timeframes
One **table/dataset per timeframe** (`tf=1m`, `tf=5m`, `tf=1h`, `tf=1d`), partitioned by **`date`** (intraday) or **`year`** (daily). Keeping timeframes physically separate avoids mixing granularities and lets a daily-bar backtest read a tiny dataset. Store **RAW (unadjusted) OHLCV** — adjustment happens at query time (§6).

```sql
-- bars schema (per timeframe dataset)
ts            TIMESTAMP   -- bar open time, UTC
symbol        VARCHAR
open          DOUBLE
high          DOUBLE
low           DOUBLE
close         DOUBLE
volume        BIGINT
vwap          DOUBLE      -- optional
trade_count   INTEGER     -- optional
-- partition: date (intraday tf) or year (daily tf); optionally symbol for very wide universes
```
Generate higher timeframes from 1m bars (or from ticks) in DuckDB with `time_bucket()` so they always reconcile. Persist the common ones (1m, 1d) for speed; derive rare ones on demand.

### (c) Point-in-time corporate-actions table (the important one)
A **separate, small, bitemporal** table. Keep it isolated so price tables stay raw and immutable, and so you can correct/restate CA history without touching prices.

```sql
-- corporate_actions schema
symbol         VARCHAR
ex_date        DATE        -- effective/ex date (the "valid time" axis)
action_type    VARCHAR     -- 'split' | 'cash_dividend' | 'stock_dividend' | 'spinoff' | 'symbol_change' | 'merger'
ratio          DOUBLE      -- splits: new/old shares (2.0 = 2:1). 1.0 if N/A
cash_amount    DOUBLE      -- dividend per share in currency. 0.0 if N/A
currency       VARCHAR
-- bitemporal "knowledge" axis — critical for no look-ahead:
announce_date  DATE        -- when the action was first publicly known
knowledge_ts   TIMESTAMP   -- when THIS ROW entered your DB (for restatements)
is_current     BOOLEAN     -- latest version of this (symbol, ex_date, action_type)
source         VARCHAR     -- vendor/provenance
```

**Why bitemporal?** Two time axes: *valid time* (`ex_date` — when the corporate event takes effect) and *knowledge/transaction time* (`announce_date` / `knowledge_ts` — when you could have known it). To avoid look-ahead you must filter on BOTH: only apply actions whose `announce_date <= as_of` AND only use the version of the record that was known as of your backtest's decision point. Vendors restate splits/dividends; storing `knowledge_ts` lets you reproduce *exactly* what you would have computed on any past date. This is what "point-in-time" really means. ([sharpely PIT](https://sharpely.in/blog/bias-free-backtesting-explained:-how-sharpely-uses-point-in-time-data-to-avoid-look-ahead-and-survivorship-bias), [QuantConnect corporate actions](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/us-equity/corporate-actions))

Add a **security master / symbology** table (also point-in-time) to handle ticker changes and survivorship (include delisted names!) — survivorship bias is the sibling of look-ahead bias.

---

## 6. On-the-fly split/dividend adjustment at query time (Key Question #3)

**Principle:** Store prices RAW. NEVER persist back-adjusted prices. Back-adjustment bakes *future* corporate actions into *past* prices → classic look-ahead bias, and it forces a full rewrite on every new split/dividend. Instead compute an **adjustment factor as a function of (symbol, date, as_of_date)** and apply it at read time. Most vendors ship back-adjusted data by default precisely because it's convenient — and that convenience is the bias. ([adventuresofgreg raw vs adjusted](http://adventuresofgreg.com/blog/2026/01/13/raw-vs-adjusted-data-backtesting/), [Palmarium adjusted vs unadjusted](https://medium.com/@contact_9367/the-good-backtest-practices-adjusted-vs-unadjusted-price-data-35e15172b509))

### Step 1 — Per-event adjustment multiplier
For each corporate action compute a single-event price multiplier `m`:
- **Split** (ratio R, new:old): price multiplier `m = 1 / R` (a 2:1 split → prices ×0.5), volume multiplier `R`.
- **Cash dividend** D on a close-before-ex price `P`: total-return price multiplier `m = (P - D) / P = 1 - D/P`.
- Combine same-day events by multiplying their `m`s.

### Step 2 — Cumulative back-adjustment factor as-of the backtest "today"
The adjustment factor on date *t*, evaluated for a backtest standing at `as_of`, is the **cumulative product of multipliers for all events with `ex_date > t` and that were KNOWN by `as_of`** (i.e. `announce_date <= as_of`). This rescales history so it's continuous up to `as_of` *without using any event you couldn't have known.* As `as_of` advances day-by-day in a walk-forward backtest, the factor for a fixed past date stays constant until a new (then-known) action appears — which is the correct, bias-free behavior.

### Step 3 — One DuckDB query (cumulative factor, then ASOF JOIN)
DuckDB's `ASOF JOIN` finds the "most-recent-preceding" factor row for each bar; window `product()`/`exp(sum(log()))` builds the cumulative factor. Sketch:

```sql
-- :as_of is the point-in-time "today" of the backtest run.
WITH known_actions AS (          -- only actions knowable at :as_of  → no look-ahead
    SELECT symbol, ex_date,
           -- per-event price multiplier (split + dividend), see Step 1
           (CASE WHEN action_type='split' THEN 1.0/ratio ELSE 1.0 END)
         * (CASE WHEN action_type='cash_dividend'
                 THEN 1.0 - cash_amount / NULLIF(prev_close,0) ELSE 1.0 END) AS m
    FROM corporate_actions ca
    WHERE ca.is_current
      AND ca.announce_date <= :as_of        -- knowledge-time filter (bitemporal)
),
factors AS (                     -- back-adjustment factor effective from each ex_date
    SELECT symbol, ex_date,
           -- product of multipliers of all LATER-or-equal events, computed via reverse cumulative product
           exp(SUM(ln(m)) OVER (
               PARTITION BY symbol ORDER BY ex_date
               ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
           )) AS adj_factor,
           ex_date AS factor_from
    FROM known_actions
)
SELECT b.ts, b.symbol,
       b.open  * COALESCE(f.adj_factor,1.0) AS adj_open,
       b.high  * COALESCE(f.adj_factor,1.0) AS adj_high,
       b.low   * COALESCE(f.adj_factor,1.0) AS adj_low,
       b.close * COALESCE(f.adj_factor,1.0) AS adj_close,
       b.volume / COALESCE(f.adj_factor,1.0) AS adj_volume,   -- volume scales inversely
       b.close AS raw_close                                    -- keep raw for sanity checks
FROM bars b
ASOF LEFT JOIN factors f
  ON b.symbol = f.symbol
 AND b.ts >= f.factor_from        -- most-recent factor effective on/before this bar
ORDER BY b.symbol, b.ts;
```

Notes:
- `ASOF LEFT JOIN ... ON equality AND ts >= factor_from` is DuckDB's exact idiom for "attach the most recent applicable value." ([DuckDB ASOF](https://duckdb.org/2023/09/15/asof-joins-fuzzy-temporal-lookups))
- Bars after the last known split/dividend get `adj_factor = NULL → COALESCE 1.0` (no adjustment), which is correct.
- Wrap this as a SQL macro / view `adjusted_bars(as_of)` and your backtester just selects from it with the current simulation date — adjustment becomes invisible and *always* point-in-time. For total-return series, use the dividend-inclusive multiplier; for price-return, use split-only.
- `prev_close` for the dividend multiplier is the raw close on the day before `ex_date`, fetched with another small ASOF/lag — precompute it into `known_actions`.

This gives institutional-grade, reproducible, look-ahead-free adjustment with **no pre-adjusted storage** and **no rewrite** when new actions arrive.

---

## 7. Is a database even needed? When does Parquet stop being enough? (Key Question #4)

**For a solo researcher on one machine: a server database is NOT needed. Parquet (source of truth) + DuckDB (SQL/as-of-join engine) + Polars (DataFrames), all Arrow-connected, is the right architecture and scales further than you think** thanks to DuckDB's out-of-core execution and Parquet pruning (validated to ~2TB on commodity hardware). ([codecentric 2TB](https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-polars-performance-and-memory-with-massive-parquet-data), [DuckDB memory mgmt](https://duckdb.org/2024/07/09/memory-management))

**"Plain Parquet only" (no DuckDB) stops being enough when you hit:**
1. **Temporal joins** — as-of joins for trades→quotes or bars→corporate-actions are painful to hand-roll in Polars and trivial in DuckDB. (This alone justifies DuckDB for *this* domain.)
2. **Transactional appends / corrections** — daily appends + vendor restatements create the "many small changes" problem; raw Parquet has no atomic multi-file update. → adopt **DuckLake** (ACID + snapshots + time-travel, still embedded).
3. **Versioning / reproducibility** — needing "what did my data look like on date X." → DuckLake snapshots (or git-LFS'd immutable Parquet partitions).
4. **Cross-file global queries** — ad-hoc SQL across the whole universe with pruning/stats. → DuckDB.

**You'd only consider a server DB (ClickHouse/QuestDB) when ALL of these become true** — none of which apply to a solo, single-machine, $0 setup:
- Multiple concurrent users / always-on shared service, or
- Real-time high-rate streaming ingestion of your own live feed (→ QuestDB for capture), or
- Data far exceeds single-machine practicality (many TB hot, needing scale-out) (→ ClickHouse).

Until then, **embedded wins.** Don't run a server you have to babysit.

---

## 8. Interop with the backtesting engine — zero-copy Arrow (Key Question #5)

Arrow is the connective tissue; design the whole platform around it so data never gets serialized between stages.

- **DuckDB ↔ Polars/Pandas:** DuckDB queries Polars/Pandas DataFrames in place and returns Arrow tables with **near-zero-copy** (shared Arrow buffers) — `con.sql(...).pl()` / `.arrow()` / `.df()`. No round-trip serialization between SQL and DataFrame land. ([DuckDB Arrow IPC](https://duckdb.org/2025/05/23/arrow-ipc-support-in-duckdb), [zero-copy joins](https://medium.com/@ThinkingLoop/duckdb-polars-zero-copy-joins-that-fly-30203084ade8))
- **Pattern for the backtester:**
  1. DuckDB does the heavy I/O + range scan + as-of adjustment over Parquet/DuckLake (out-of-core, multithreaded).
  2. Hand the result to the engine as an **Arrow table / Polars DataFrame** (zero-copy) for vectorized signal computation.
  3. Feed NumPy views (zero-copy from Arrow for primitive columns) into vectorized strategy/stat code, or stream row-batches for event-driven simulation.
- **Why this matters:** in fast pipelines the bottleneck is usually *moving data between tools*; Arrow removes that copy. It also future-proofs you — if you later add ClickHouse/QuestDB, both can export Arrow, so the research engine interface is unchanged.
- **Event-driven backtests:** pull per-symbol Arrow record batches and iterate; **vectorized backtests:** materialize the adjusted Polars/Arrow frame once and compute over columns. Both stay zero-copy from storage.

---

## 9. Final recommendation & rollout

**Adopt now (Phase 1 — simplest thing that's correct):**
1. **Parquet** (ZSTD) as immutable source of truth, **Hive-partitioned**: trades/quotes by `symbol/date`; bars by `tf` then `date`/`year`.
2. **DuckDB** as the embedded SQL + as-of-join + range-scan engine. No server.
3. **Polars** for in-memory feature engineering; **Arrow** for zero-copy hand-off to the backtester.
4. **Separate bitemporal corporate-actions table** + **security master**; prices stay RAW; adjustment via the §6 `ASOF JOIN` cumulative-factor view, parameterized by `as_of`.

**Upgrade when needed (Phase 2):**
5. Migrate managed tables (bars, corporate_actions) to **DuckLake** for ACID appends, snapshots, and time-travel — keeps everything embedded, adds reproducibility/versioning. This is the free, SQL-native answer to what made ArcticDB attractive.

**Explicitly rejected for this project:**
- **ClickHouse** — overkill; server/ops tax for scale-out/concurrency you don't have.
- **ArcticDB** — superb tech but **BSL license conflicts with the $0/free + economic-benefit reality**; do not build the foundation on that ambiguity.
- **QuestDB / TimescaleDB** — server-based; solve live-ingest / relational-Postgres problems that aren't your bottleneck. (Reconsider QuestDB only if you start capturing your own live high-rate tick feed.)

---

## Sources

**DuckDB vs ClickHouse / single-node analytics**
- https://oneuptime.com/blog/post/2026-03-31-clickhouse-vs-duckdb-analytical-workloads/view
- https://www.tinybird.co/blog/clickhouse-vs-duckdb-nodes
- https://www.dench.com/blog/duckdb-vs-clickhouse
- https://www.cloudraft.io/blog/clickhouse-vs-duckdb
- https://www.timestored.com/data/time-series-database-benchmarks

**Time-series DB benchmarks (treat vendor posts skeptically)**
- https://kx.com/blog/benchmarking-kdb-x-vs-questdb-clickhouse-timescaledb-and-influxdb-with-tsbs/
- https://questdb.com/blog/timescaledb-vs-questdb-comparison/
- https://www.timestored.com/data/questdb-for-tick-data-2025
- https://db-engines.com/de/system/PostgreSQL%3BQuestDB%3BTimescaleDB

**DuckDB capabilities (partitioning, ASOF, Arrow, memory, compression)**
- https://duckdb.org/docs/lts/data/partitioning/hive_partitioning
- https://duckdb.org/2023/09/15/asof-joins-fuzzy-temporal-lookups
- https://duckdb.org/2025/05/23/arrow-ipc-support-in-duckdb
- https://duckdb.org/2024/07/09/memory-management
- https://duckdb.org/docs/current/guides/performance/how_to_tune_workloads
- https://duckdb.org/2022/10/28/lightweight-compression
- https://duckdb.org/2025/01/22/parquet-encodings
- https://duckdb.org/docs/current/data/parquet/overview
- https://dev.to/prithwish_nath/the-practical-limits-of-duckdb-on-commodity-hardware-f76
- https://www.codecentric.de/en/knowledge-hub/blog/duckdb-vs-polars-performance-and-memory-with-massive-parquet-data
- https://medium.com/@ThinkingLoop/duckdb-polars-zero-copy-joins-that-fly-30203084ade8

**DuckLake**
- https://ducklake.select/
- https://ducklake.select/2026/04/13/ducklake-10/
- https://www.theregister.com/2026/04/16/duckdb_uses_rdbms_lakehouse/
- https://motherduck.com/learn/partitioned-writes-parquet-ducklake/

**ArcticDB (tech + license)**
- https://github.com/man-group/ArcticDB
- https://docs.arcticdb.io/4.5.0/faq/
- https://docs.arcticdb.io/latest/licensing/
- https://github.com/man-group/ArcticDB/blob/master/LICENSE.txt
- https://www.tldrlegal.com/license/business-source-license-bsl-1-1
- https://arcticdb.io/

**Corporate actions / point-in-time / look-ahead bias**
- http://adventuresofgreg.com/blog/2026/01/13/raw-vs-adjusted-data-backtesting/
- https://medium.com/@contact_9367/the-good-backtest-practices-adjusted-vs-unadjusted-price-data-35e15172b509
- https://sharpely.in/blog/bias-free-backtesting-explained:-how-sharpely-uses-point-in-time-data-to-avoid-look-ahead-and-survivorship-bias
- https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/us-equity/corporate-actions
