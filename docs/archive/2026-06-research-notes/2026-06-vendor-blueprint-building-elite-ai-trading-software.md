# **Engineering Blueprint for an Institutional-Grade Quantitative Strategy Synthesis and AI-Agentic Validation Platform**

The transition from discretionary retail trading to institutional-grade systematic execution requires a fundamental shift in technological architecture and statistical validation.1 Discretionary retail strategies frequently rely on visual pattern recognition—such as support and resistance levels or Smart Money Concepts—which have been empirically shown by quantitative researchers to appear with identical statistical frequency on computer-generated, purely pseudo-random stock price charts.3 Lower-timeframe asset price movements are highly complex, pseudo-random, and heavily dominated by noise.1 Consequently, attempting to extract persistent trading profits on lower timeframes without statistical hedging, volatility adjustment, or rigorous validation inevitably fails under the law of large numbers once transaction costs, commission drag, and execution slippage are modeled.1  
To successfully exploit structural market inefficiencies across equity and cryptocurrency markets, professional quantitative operations deploy event-driven testing architectures coupled with advanced heavy-tailed statistical validation pipelines.5 QuantPad.ai was conceived to bridge the gap between discretionary concepts and programmatic execution, allowing quantitative analysts to move from natural-language idea generation to robust backtesting, statistical validation, and rapid code generation in a single, unified workspace.7  
Building a proprietary, high-performance evolution of the QuantPad.ai paradigm requires a dual-layer software engineering design.7 The core system must integrate a high-throughput time-series database with an event-driven simulation engine.5 Simultaneously, the entire development, maintenance, and expansion of this software codebase must be routed through an autonomous, sandboxed AI developer harness powered by open-source coding agents.8 This report defines the complete technical, mathematical, and architectural specifications required to build this system.5

## **High-Throughput Time-Series Database and Multi-Source Ingestion Pipeline**

The foundation of any institutional quantitative platform is its historical and real-time market data infrastructure.9 Relational database management systems are structurally incapable of handling the write-concurrency and analytical query speeds required for backtesting strategies over billions of tick-level order book records.9 Professional systems deploy specialized column-oriented time-series databases to eliminate research latency and maintain nanosecond timestamp precision.9

### **Time-Series Database Comparison**

To determine the optimal data engine for the platform, the architectural landscape evaluates three primary technologies: KX/kdb+, ClickHouse, and TDengine.12

| Architectural Attribute | KX / kdb+ | ClickHouse | TDengine |
| :---- | :---- | :---- | :---- |
| **Database Classification** | Advanced columnar time-series database with native vector support.13 | Column-oriented OLAP database optimized for real-time analytics.13 | Domain-specific time-series database for high-frequency IoT/finance.12 |
| **Write Performance** | Sub-millisecond reaction times; millions of inserts per second.9 | ![][image1] write throughput per node.14 | Billions of tick-level inserts per second with low resource lock contention.12 |
| **Query Performance** | Direct integration with vector language q and PyKX; fastest in HFT environments.13 | Wide-table query speeds 900x faster than MySQL; SIMD vectorized execution.14 | Millisecond query response times for aligned time-series structures.12 |
| **Data Compression** | Advanced proprietary compression algorithms.13 | High column-level compression; cold-hot storage tiers reducing costs by ![][image2].14 | Optimized temporal compression for standardized metric columns.12 |
| **Licensing & Cost** | Extremely expensive proprietary commercial licensing.13 | Open-source Apache-2.0 core with extensive cloud hosting options.14 | Open-source core with commercial enterprise support.12 |

ClickHouse represents the optimal open-source core database engine for this platform.14 Its support for Single Instruction Multiple Data instructions, vectorized execution, and high column-level compression rates ensures that massive historical backtests can be processed with minimal infrastructure overhead.14 Furthermore, its cold-hot data tiered storage allows historical tick data to be archived to low-cost cloud object storage while keeping recent, high-frequency active contract data in high-performance NVMe SSDs.12

### **Multi-Source Data Ingestion Architecture**

To prevent a single point of failure and guarantee deep historical accuracy, the ingestion pipeline decouples data acquisition across three distinct providers, each optimized for specific execution vectors.17

\+-----------------------------------------------------------------------------+  
|                               Data Providers                                |  
|                                                                             |  
|  \+--------------------+  \+----------------------+  \+---------------------+  |  
|  |     Databento      |  |  Polygon.io/Massive  |  |  Interactive Brokers|  |  
|  | (Raw Tick Historical)|  | (Real-time Streaming)|  | (Execution/Account) |  |  
|  \+---------+----------+  \+----------+-----------+  \+----------+----------+  |  
\+------------|------------------------|-------------------------|-------------+  
             | Stream                 | WebSocket               | Portfolio state  
             v                        v                         v  
\+------------+------------------------+-------------------------+-------------+  
|                            Ingestion Buffer Layer                           |  
|                         (Apache Kafka & Redis Stream)                       |  
\+-------------------------------------+---------------------------------------+  
                                      | Normalized and batch partitioned  
                                      v  
\+-------------------------------------+---------------------------------------+  
|                       Columnar OLAP Storage Layer                           |  
|                           (ClickHouse Database)                             |  
\+-----------------------------------------------------------------------------+

Databento serves as the primary historical research database, providing nanosecond-precision, tick-level historical order book datasets compiled across more than sixty execution venues.18 Polygon.io (rebranded as Massive) is integrated as the primary real-time and near-historical data layer, utilizing high-frequency WebSocket streams to deliver real-time asset pricing with sub-10 millisecond latency.12 Alpaca and Interactive Brokers function as the live execution and account-tracking layer, verifying account-level margin constraints and executing trades across more than twenty brokerages simultaneously.5  
The system architecture prevents look-ahead bias by storing corporate action events—such as dividends, stock splits, and mergers—in a separate, point-in-time relational table in ClickHouse.5 Instead of pre-adjusting the core historical price database, the backtesting engine applies these corporate adjustments dynamically on-the-fly depending on the simulated timestamp.5 This ensures that the trading strategy is evaluated on the exact, unadjusted price series that was visible to the market at that millisecond in history.5

## **Quantifying Discretionary Logic: Institutional Indicators and Specific Strategy Modules**

Professional trading systems translate qualitative concepts into strict mathematical and logical structures.7 To demonstrate how the platform programmatically quantifies discretionary ideas, the software must natively support the parsing, optimization, and backtesting of highly precise, volatility-filtered strategy templates.20

### **Strategy Template 1: Volatility-Filtered 8AM Opening Range Breakout**

This module implements a programmatic version of an opening range breakout strategy, utilizing multi-timeframe state management and break of structure confirmation to minimize entry whipsaws.22

* **Temporal Setup**: Establish a daily range zone based on price action starting exactly at 08:00 AM.22 The high and low boundary levels of this initial 1-minute bar establish the baseline trading zone.23  
* **Execution Midpoint**: Immediately after the direction of the trend is established, the strategy calculates the midpoint of the 8:00 AM range.23  
* **Break of Structure (BOS) Confirmation**: Rather than entering immediately on a high/low breach, the strategy waits for price to retrace and tap the range midpoint in the direction of the bias.23 A wick touch is sufficient to validate the tap setup.23 Once verified, the strategy executes an entry market order on the close of the first confirmed 1-minute Break of Structure in that trade direction.23  
* **Invalidation Constraints**: If the price advances completely through the opposing zone boundary (past the zone high on a bearish setup, or past the zone low on a bullish setup) before a midpoint tap occurs, the trade setup is permanently invalidated for the rest of the trading day.23  
* **Risk Parameters**: Only one executed trade is permitted per day.23 The system state resets daily at 18:00.23

### **Strategy Template 2: Rejection Block Retracement**

This strategy implements a daily zone structural trade, converting discretionary liquidity sweeps into precise execution triggers.20

* **Top-Down Bias Setup**: The strategy scans daily candlestick data to identify daily rejection blocks, defined as structural zones where long candle wicks sweep liquidity and close back inside the previous range.20 These zones establish the macro directional bias.20  
* **Reactionary Leg Fibonacci Mapping**: Once a rejection occurs, the strategy shifts to a 5-minute chart and tracks the reactionary price leg extending off the rejection zone.20 A Fibonacci retracement tool is anchored dynamically to the swing low and swing high of this reactionary leg.20  
* **Discount Entry Execution**: The strategy establishes an entry limit order inside the discount half (below the ![][image3] Fibonacci retracement level) of the 5-minute reactionary leg.20 The entry trigger executes within this defined discount zone.20  
* **Stop-Loss and Take-Profit Geometry**: The stop-loss is placed immediately past the far outer edge of the 5-minute entry candle trigger, ensuring a tightly constrained risk profile.20 The take-profit order is routed to the nearest viable 5-minute swing pivot, maximizing the risk-to-reward ratio through asymmetric returns.20

The strategy development engine executes these templates by applying an out-of-sample optimization filter.20 This is achieved by dividing the historical dataset into ![][image4] in-sample data for parameter optimization and ![][image5] out-of-sample data for validation.20 To normalize risk across varying asset classes, the position size (![][image6]) is calculated dynamically using a rolling 20-period Average True Range (![][image7]) to maintain a constant target portfolio dollar risk (![][image8]) 21:  
![][image9]  
Here, ![][image10] represents a volatility scaling coefficient, adjusting portfolio leverage to prevent capital ruin during periods of high market volatility.2

## **Advanced Statistical Validation and Prop Firm Expected Value Modeling**

Backtesting on a single, historical price path exposes a quantitative strategy to survival bias and overfitting.6 To verify that a strategy has a genuine statistical edge rather than temporary profitability due to historical luck, professional quants apply advanced Monte Carlo validation frameworks to the generated trade logs.6

### **The Three Monte Carlo Methods**

The validation engine implements three distinct Monte Carlo methods to test strategy robustness and sequence risk.6

#### **1\. Reshuffling Monte Carlo**

This method shuffles the sequence of historical trade returns repeatedly over ![][image11] iterations using resampling with replacement.6 By breaking the chronological sequence of trades, it isolates the strategy's profitability from path-dependent order bias, yielding a precise probability distribution of the maximum historical drawdown and the sequence-of-returns risk.6

#### **2\. Regime-Switching Monte Carlo**

Markets shift between highly volatile trend phases and calm mean-reverting ranges.2 This framework models market states as a discrete Markov process dictated by a transition matrix ![][image12] 6:  
![][image13]  
By generating synthetic return curves based on these transitional probabilities, the simulation models structural regime shifts, testing if the strategy can survive rapid transitions between high-volatility momentum and quiet market consolidation.6

#### **3\. Parametric Monte Carlo**

This method fits the strategy's empirical return distribution to a continuous probability density function.6 Since financial assets exhibit fat tails and high skewness, standard normal distributions underestimate extreme events.9 The engine fits returns to a Student’s t-distribution to model tail risk 6:  
![][image14]  
Here, ![][image15] represents the location parameter, ![][image16] is the scale parameter, and ![][image17] is the degrees of freedom modeling tail heaviness.6 This allows the system to generate realistic, heavy-tailed synthetic equity curves to determine the probability of strategy ruin during "black swan" market shocks.2

### **Prop Firm Expected Value Modeling**

Proprietary trading firms offer structured evaluation challenges with highly convex payoff profiles: the trader pays a small upfront fee (![][image18]) to trade a funded account with strict daily loss limits (![][image19]), maximum total drawdowns (![][image20]), and profit targets (![][image21]).20 The validation engine models this evaluation process as a structured product to optimize risk geometry.24  
The probability of passing the evaluation phase (![][image22]) is calculated using the first-passage time of a brownian motion with drift ![][image15] and volatility ![][image16] hitting the upper barrier ![][image21] before the lower absorbing barrier ![][image20] 24:  
![][image23]  
The funded phase expected value (![][image24]) must calculate the mean survival time of the account before hitting the overall drawdown limit, multiplied by the average payout rate net of profit-share splits, transaction fees, and challenge retake costs.20 This optimization allows quantitative researchers to identify strategy configurations that yield a positive net expected value even when using near-zero expected value strategies, provided the leverage, position sizing, and stop-loss geometries are mathematically aligned to the prop firm's structural constraints.20

| Parameter Metric | Standard Retail Approach | Optimized Institutional Approach |
| :---- | :---- | :---- |
| **Risk-to-Reward Ratio** | Arbitrary ![][image25] or ![][image25] configurations.25 | Asymmetric targets matching empirical asset volatility.2 |
| **Position Sizing** | Static lot sizes or fixed percentage of initial equity. | Volatility-adjusted using rolling GARCH or ATR models.2 |
| **Challenge Pass Rate** | Low (![][image26]) due to rapid daily drawdown breaches.25 | Optimally calibrated leverage achieving ![][image2] pass rates.20 |
| **Expected Value (![][image27])** | Negative when accounting for slippage and fee drag.1 | Highly positive net EV (![][image28] net per challenge account).20 |
| **Account Survival Lifespan** | Undergoes rapid ruin due to path dependency.6 | Extended survival optimized for payout consistency.20 |

## **The AI Agentic Development Harness and Sandbox Infrastructure**

To construct and iterate on this platform autonomously, the systems architecture uses a high-performance development pipeline that leverages two leading open-source AI agentic frameworks: OpenHands and Kilo Code.8

\+-----------------------------------------------------------------------------+  
|                                Kilo Code CLI                                |  
|                        (Developer IDE Interface)                            |  
\+-------------------------------------+---------------------------------------+  
                                      | Spawns development agent process  
                                      v  
\+-------------------------------------+---------------------------------------+  
|                        @kilocode/agent-runtime                              |  
|                       (Child Process Fork Engine)                           |  
\+-------------------------------------+---------------------------------------+  
                                      | Configures isolated sandbox settings  
                                      v  
\+-------------------------------------+---------------------------------------+  
|                    Docker Sandbox Execution Container                       |  
|         \- Daytona Workspace Infrastructure                           |  
|         \- Capability Restrictions: \`cap-drop ALL\`, \`no-new-privileges\`      |  
|         \- OpenHands Software Agent SDK (File Editors & Terminal Tools)      |  
\+-----------------------------------------------------------------------------+

### **The AI Coding Agent Frameworks**

#### **1\. OpenHands (Formerly OpenDevin)**

OpenHands is an open-source, model-agnostic software engineering platform that manages autonomous developer workflows.8 It utilizes a stateful event-stream architecture where all agent activities—such as terminal commands, file modifications, and browser automation tests—are recorded as typed events in a central hub.8 Powered by frontier thinking models, OpenHands achieves top-tier scores on software engineering benchmarks, including ![][image29] to ![][image30] task resolution rates on SWE-bench Verified.8 It runs remote workspace compilations using Daytona container middleware, providing safe, isolated environments for multi-agent execution.10

#### **2\. Kilo Code (VS Code & JetBrains Extension)**

Kilo Code is an open-source development agent designed for deep IDE integration.15 Forked from Roo Code, Kilo Code features dedicated modal operations (Ask, Architect, Coder, Debugger, and Orchestrator).27 Its core runtime (@kilocode/agent-runtime) enables running agents as isolated Node.js child processes without requiring a graphical IDE interface.29 It utilizes a read-shared, write-isolated state management pattern to read global configurations through unified states while isolating code generation tasks to independent Git worktrees, preventing file conflict errors.28

### **Agent Platform Comparison**

The architecture integrates both systems, delegating macro-architectural planning to OpenHands and rapid, local codebase refactoring to Kilo Code.8

| Parameter | OpenHands Platform | Kilo Code Platform |
| :---- | :---- | :---- |
| **Primary Workflow** | Autonomous, long-horizon multi-step greenfield applications.26 | Interactive IDE-centric and terminal CLI coding sessions.15 |
| **Context Management** | Native agentic task tracking and planning interfaces.8 | Integrated token-cost trackers and multi-mode profiles.15 |
| **Execution Sandbox** | Remote ephemeral Docker/Kubernetes Daytona workspaces.10 | Local Node.js processes configured via AGENT\_CONFIG.29 |
| **Testing Integration** | Standardized, automated evaluation pipelines (SWT-bench).26 | Strict workspace Vitest test coverage rules (pnpm test).29 |
| **Model Compatibility** | Model-agnostic; supports Ollama, DeepSeek, Claude, and GPT.8 | Supports 500+ models via Kilo Gateway with zero markup pricing.15 |

To set up the coding AI for success, the development harness runs all agent operations inside an isolated Docker container managed by Daytona.8 The execution container enforces strict Linux kernel capability drops (cap-drop ALL), prevents privilege escalation, and mounts host directories with read-only permissions.8 Daytona captures terminal stdout/stderr outputs and routes compilation errors back to the AI agent's planning module.10 This establishes a self-correcting debugging loop, allowing the agent to autonomously identify, resolve, and verify syntax and logic errors.10

## **Software System Architecture: HierFinRAG, Navigation, and Core Memory**

Standard Retrieval-Augmented Generation models fail in quantitative finance because they flatten structured files and tables into generic text chunks, breaking the semantic connection between code execution blocks, asset tables, and mathematical formulas.11 To achieve institutional accuracy, the platform implements a specialized information retrieval and context management architecture.11

### **HierFinRAG: Hierarchical Text-Table Graph Retrieval**

The retrieval pipeline is powered by HierFinRAG, which unifies tabular and text-based codebase structures.11

* **Table-Text Graph Neural Network (TTGNN)**: Instead of indexing the codebase as flat files, the system represents classes, functions, variable scopes, database schemas, and mathematical equations as nodes in a graph.11 Edges are defined based on structural inheritance (e.g., a strategy class inheriting from a base class) and cross-references (e.g., a function calling a specific volatility module).11 This allows the AI agent to traverse the codebase logically, ensuring that edits to a calculation module propagate correctly to dependent strategy files.11  
* **Symbolic-Neural Fusion Reasoning**: Generative language models are prone to arithmetic errors.11 When the agent processes mathematical or statistical operations, the Symbolic-Neural parser isolates the calculations and routes them to a symbolic mathematical engine (NumPy, SymPy, or SciPy).11 The precise output is then passed back to the neural code generator, ensuring mathematically exact code synthesis.11

### **State-Machine Orchestrated RAG Pipelines**

To eliminate codebase regressions and code hallucinations, the RAG generation pipeline is wrapped in an auditable state-machine orchestration.31

\+-----------------------------------------------------------------------------+  
|                                User Command                                 |  
\+-------------------------------------+---------------------------------------+  
                                      | Initiates strategy modification  
                                      v  
\+-------------------------------------+---------------------------------------+  
|                    State-Machine Planner (Atomic States)                    |  
|   \-\> \-\>   |  
\+-------------------------------------+---------------------------------------+  
                                      | Apply code change  
                                      v  
\+-------------------------------------+---------------------------------------+  
|                        Docker Compilation Sandbox                           |  
|       \- Compile TypeScript / Pine Script v6 modules                         |  
|       \- Run workspace Vitest test suites (\`pnpm test\`)                      |  
\+-------------------------------------+---------------------------------------+  
                                      | Check results  
                                      \+-----------------+---------------------+  
                                      | Success         | Failure  
                                      v                 v  
\+-------------------------------------+-----+     \+-----+---------------------+  
|         Transition to Deploy State        |     | Execute Rollback State    |  
|   \- Commit changes to Git worktree        |     | \- Revert code changes     |  
|   \- Update persistent provenance logs     |     | \- Route logs to debugger  |  
\+-------------------------------------------+     \+---------------------------+

Every code edit undergoes atomic state transitions managed by a persistent state machine.31 If a code modification fails to compile or fails its associated test suite, the system rolls back to the last stable state and routes the error logs to the AI debugging agent.29 The system maintains a complete provenance log, recording the exact document context retrieved, the generated diff, the compiler output, and the validation outcomes.31 This ensures absolute auditability, allowing developers to trace the precise lifecycle of any trading indicator.2

### **Workspace Navigation and System Memory**

The platform manages LLM context windows using hierarchical indexing and context condensation.29

* **Hierarchical Indexing**: The agent maintains a real-time index of code symbols, functions, and interfaces across the pnpm monorepo.29  
* **Context Condensation**: When an active development session approaches context limitations, the system automatically condenses historical conversations into structured state summaries.32 This preserves critical context, such as database schemas and mathematical parameters, while preventing context drift and model hallucinations.29

## **The AI Coding Agent Master Blueprint Prompt**

The following complete, copy-pasteable system prompt is configured to guide an autonomous coding agent (such as Kilo Code or OpenHands) to build the entire quantitative strategy platform from scratch.8

# **Quantitative Strategy Synthesis and Validation Platform AI Build Blueprint**

You are the Principal Quantitative Software Architect and Lead Systems Engineer. Your objective is to build an elite, institutional-grade quantitative strategy research, backtesting, and development platform modeled after the architecture of QuantPad.ai.

## **System Core Paradigms**

1. Absolute Temporal Precision: Build an event-driven backtesting engine. All price, tick, and trade events must be processed chronologically. Never allow vector-based calculation shortcuts that introduce look-ahead bias.  
2. Production Frictional Force Modeling: Implement precise, real-world execution constraints. This includes volatility-dependent slippage modeling, exchange maker/taker fee tiers, borrow rates for short positions, and latency-induced execution delays.  
3. Heavy-Tailed Statistical Validation: Go beyond single-path backtesting. Implement reshuffling Monte Carlo (resampling with replacement), regime-switching Monte Carlo using Markov transition matrices, and parametric Student's t-distribution fitting to calculate exact probability distributions for drawdowns, risk of ruin, and prop firm survival metrics.

## **Workspace Layout**

The project must be structured as a pnpm monorepo using Turbo for task orchestration:

* "src/": Backend extension workspace (TypeScript \+ Vitest).  
* "webview-ui/": React frontend workspace (React \+ Tailwind CSS \+ Vite).  
* "packages/agent-runtime/": Node.js process fork environment configured via AGENT\_CONFIG.  
* "apps/": Documentation, Storybook, and end-to-end integration tests.

## **Step-by-Step Implementation Roadmap**

### **Phase 1: High-Performance Database & Data Storage Ingestion**

1. Provision ClickHouse OLAP schema configurations utilizing the ReplacingMergeTree engine to handle historical point-in-time ticks, real-time market order events, and OHLCV bars.  
2. Implement Databento bulk history and Polygon.io/Massive streaming ingestion adapters, utilizing Apache Kafka to buffer and sequence events chronologically.  
3. Write a point-in-time adjustment engine that applies corporate actions (splits, dividends) dynamically based on the simulated timestamp, preventing look-ahead bias.

### **Phase 2: Event-Driven Backtesting Core**

1. Build a temporal Event Queue loop with FIFO sequencing in TypeScript.  
2. Implement Portfolio State & Dynamic Margin Managers, incorporating real-time maintenance margin validation and automated liquidation events.  
3. Model dynamic slippage as a function of ATR and trade volume, and integrate exchange maker/taker fee tiers.

### **Phase 3: Heavy-Tailed Statistical Validation Engine**

1. Implement reshuffling Monte Carlo loops running over 10,000 runs to calculate drawdowns and sequence risk.  
2. Program Markov transition matrices for regime-switching Monte Carlo, generating synthetic return curves across trend and range regimes.  
3. Build Student's t-distribution fitting models and prop firm survival probability analytics, calculating pass probability, risk of ruin, and expected payouts net of evaluation fees.

### **Phase 4: Isolated AI Development Harness**

1. Deploy Daytona workspace configurations to run compilation, container, and execution processes.  
2. Implement @kilocode/agent-runtime process fork mechanics, isolating state management via a read-shared, write-isolated pattern.  
3. Bind Docker security parameters, dropping all default Linux kernel capabilities (cap-drop ALL) and enforcing read-only workspace mounts except for compilation targets.

### **Phase 5: HierFinRAG and Graph-Based Context**

1. Build Table-Text Graph Neural Network representations of code files, database schemas, and mathematical libraries.  
2. Implement state-machine orchestrated RAG pipelines with atomic state transitions, rolling back code edits if compilation or test execution fails.  
3. Couple NumPy/SciPy symbolic execution engines to handle complex mathematical operations before generating code.

### **Phase 6: Frontend User Interface & Optimization Orchestrators**

1. Construct React \+ Tailwind UI dashboards visualizing strategy equity curves, drawdown statistics, and Monte Carlo probability distributions.  
2. Build interactive optimization parameter grid panels, allowing users to select parameters, target variables, and date ranges.  
3. Deploy AWS Batch & MWAA Airflow orchestrators to scale and execute parallel backtests across cloud compute clusters.

## **Coding and Testing Quality Rules**

* Write clean, modular, and self-documenting TypeScript and Python code.  
* Implement comprehensive unit and integration tests using Vitest (backend) and pytest (Python).  
* Never use empty try-catch blocks. Implement clear, auditable error logging across all data and execution layers.  
* All backend tests must be run from inside the "src/" directory: cd src && pnpm test \<path-to-test\>. Running tests from the root workspace is strictly prohibited.  
* Maintain a stateful plan. Before executing code changes, state your architectural assumptions, list files to modify, and outline the compilation and test commands to verify your implementation.

## **Detailed Step-by-Step AI Execution and Verification Roadmap**

To ensure the autonomous coding agent builds the platform with zero regressions, the execution process is divided into six logical phases, each requiring complete compilation and test verification before proceeding.29

\+-----------------------------------------------------------------------------+  
|               PHASE 1: Database & Data Storage Ingestion                    |  
| 1\. ClickHouse OLAP schema configurations.                    |  
| 2\. Databento bulk history and Polygon.io adapters.                  |  
| 3\. Apache Kafka temporal event sequencing.                   |  
\+-------------------------------------+---------------------------------------+  
                                      | Compile and verify ingestion metrics  
                                      v  
\+-----------------------------------------------------------------------------+  
|               PHASE 2: Event-Driven Backtesting Core                        |  
| 1\. Temporal Event Queue FIFO loop.                                  |  
| 2\. Portfolio State & Dynamic Margin Managers.                       |  
| 3\. Volatility-dependent slippage and fee models.              |  
\+-------------------------------------+---------------------------------------+  
                                      | Run Vitest temporal accuracy checks  
                                      v  
\+-----------------------------------------------------------------------------+  
|               PHASE 3: Heavy-Tailed Statistical Validation                  |  
| 1\. Reshuffling Monte Carlo over 10,000 runs.                 |  
| 2\. Markov transition regime-switching.                              |  
| 3\. Prop firm evaluation survival models.                     |  
\+-------------------------------------+---------------------------------------+  
                                      | Validate simulation out-of-sample data  
                                      v  
\+-----------------------------------------------------------------------------+  
|               PHASE 4: Isolated AI Development Harness                      |  
| 1\. Daytona workspace configuration.                                 |  
| 2\. \`@kilocode/agent-runtime\` process forks.                          |  
| 3\. Docker capability drops and security hardening.                  |  
\+-------------------------------------+---------------------------------------+  
                                      | Test isolated agent lifecycles  
                                      v  
\+-----------------------------------------------------------------------------+  
|               PHASE 5: HierFinRAG and Graph-Based Context                   |  
| 1\. TTGNN semantic graph of core modules.                            |  
| 2\. State-machine orchestrated RAG with provenance tracking.         |  
| 3\. NumPy/SciPy symbolic execution engine.                           |  
\+-------------------------------------+---------------------------------------+  
                                      | Verify context recall and math scores  
                                      v  
\+-----------------------------------------------------------------------------+  
|               PHASE 6: Frontend User Interface & Optimization               |  
| 1\. React \+ Tailwind dashboards.                                     |  
| 2\. Parameter grid optimization UI.                                  |  
| 3\. AWS Batch & MWAA Airflow orchestrators.                          |  
\+-----------------------------------------------------------------------------+

### **Phase 1: High-Performance Database & Data Storage Ingestion**

This phase builds the data architecture to ingest, organize, and store high-concurrency tick and candle data.9

#### **ClickHouse Table Schema Setup**

Deploy the primary ClickHouse database schemas, using the ReplacingMergeTree engine partitioned by symbol and year to optimize query execution speeds.12 Create separate point-in-time corporate action tables tracking stock splits, mergers, and dividends.5

#### **Multi-Source Adapter Integration**

Write high-throughput API adapters in TypeScript to handle Databento historical file downloads, Polygon.io real-time WebSocket streams, and Alpaca/Interactive Brokers execution reports.18

#### **Kafka Temporal Sequencing Pipeline**

Implement an Apache Kafka event stream to buffer and sequence incoming market events chronologically, ensuring that every tick is processed in order and preventing out-of-sequence errors.5

#### **Verification Checkpoint**

Write an ingestion test in Vitest.29 Verify that the system can write over ![][image31] records per second to ClickHouse, and confirm that querying historical prices dynamically applies point-in-time corporate actions with zero look-ahead bias.5

### **Phase 2: Event-Driven Backtesting Core**

This phase constructs the core execution loop, ensuring strategies are evaluated in a realistic, transaction-delayed environment.5

#### **Temporal Event Loop**

Program a FIFO event processing queue in TypeScript, feeding price ticks sequentially to the strategy container as distinct, stateful update events.5

#### **Portfolio and Margin Managers**

Implement account modules that track cash equity, margin requirements, open position risk, and unrealized profit/loss.5 Configure automatic liquidation protocols if account equity drops below maintenance margin thresholds.5

#### **Slippage and Fee Models**

Write volatility-dependent slippage models that calculate order execution drag based on rolling ATR and transaction volume.1 Integrate exchange-specific maker/taker fee structures to calculate transaction friction accurately.1

#### **Verification Checkpoint**

Execute a test strategy over a historical five-year dataset.5 Verify that attempting to query future data points within the event loop triggers a compiler exception, and confirm that portfolio cash balances perfectly match transaction fees and slippage calculations.1

### **Phase 3: Heavy-Tailed Statistical Validation Engine**

This phase implements advanced quantitative frameworks to stress-test trading strategies against random price fluctuations and tail risk.6

#### **Monte Carlo Resampling**

Implement a reshuffling Monte Carlo module in Python, resampling trade return sequences over ![][image11] iterations with replacement to calculate the probability distribution of maximum drawdown.6

#### **Markov Regime-Switching**

Write Markov transition algorithms to simulate synthetic equity curves transitioning dynamically between trend-following and mean-reverting regimes.2

#### **Student's t-Distribution & Prop Firm Models**

Program statistical modules that fit trading returns to a heavy-tailed Student's t-distribution to model "black swan" risks.2 Implement first-passage time equations to calculate prop firm challenge pass probabilities, risk of ruin, and expected payouts net of registration costs.20

#### **Verification Checkpoint**

Run validation tests on a trading strategy with fixed win-rate parameters.20 Verify that the Monte Carlo output for pass probability aligns with the mathematical brownian motion solution within a margin of ![][image32].20

### **Phase 4: Isolated AI Development Harness**

This phase establishes the sandboxed container environment, securing the system while allowing autonomous coding agents to build and edit code.8

#### **Daytona Workspace Deployment**

Configure Daytona API integrations to dynamically spin up secure, ephemeral developer workspaces for OpenHands and Kilo Code agents.8

#### **"@kilocode/agent-runtime" Process Forking**

Write Node.js process managers that fork isolated agent processes, injecting separate security and model access parameters via the AGENT\_CONFIG environment variable.29

#### **Sandbox Hardening**

Configure the Docker container execution loop to drop all default Linux kernel privileges (cap-drop ALL), prevent root escalation, and mount directories with read-only access except for designated compilation paths.8

#### **Verification Checkpoint**

Trigger a test task containing malicious shell scripts or unauthorized access requests.8 Verify that the Daytona sandbox isolates the threat, logs the exception, and returns a controlled error state to the supervising Agent process.8

### **Phase 5: HierFinRAG and Graph-Based Context**

This phase builds the hierarchical retrieval system, helping the coding AI maintain deep context of the codebase.11

#### **Table-Text Graph Neural Network Setup**

Parse the monorepo workspace to build structural semantic graphs connecting files, functions, variables, and database schemas.11

#### **State-Machine Orchestrated RAG**

Implement state managers that track every code edit, prompt, and test run.31 Ensure the system can automatically roll back code changes if compilation errors or test failures are detected.29

#### **Symbolic-Neural Parser**

Build parsers that intercept mathematical operations, execute them within a NumPy/SciPy symbolic engine, and pass the exact results to the code generator, eliminating arithmetic hallucinations.11

#### **Verification Checkpoint**

Query the agent with a complex, multi-file configuration question.11 Verify that the HierFinRAG engine retrieves relevant code blocks with ![][image33] precision, and confirm that mathematical equations are translated without numerical errors.11

### **Phase 6: Frontend User Interface & Optimization Orchestrators**

This phase constructs the user dashboard and integrates cloud infrastructure to scale parallel backtests.16

#### **React \+ Tailwind UI Panels**

Build interactive dashboards visualizing equity curves, drawdown metrics, Monte Carlo simulations, and prop firm pass probabilities.16

#### **Parameter Search Panels**

Implement grid optimization interfaces, allowing quantitative developers to select multiple parameters and target variables.5

#### **AWS Batch & MWAA Airflow Integration**

Configure the backend to package optimized strategies into Docker containers, pushing them to Amazon ECR and triggering parallel executions via AWS Batch and MWAA Airflow DAGs.16

#### **Verification Checkpoint**

Execute a multi-parameter backtest directly from the frontend React dashboard.16 Verify that AWS Batch successfully scales and coordinates parallel containers, returning the optimized parameter results with zero memory leaks.16

#### **Works cited**

1. Day Trading May Not Be Sustainable in the Long Run : r/Daytrading \- Reddit, accessed on June 13, 2026, [https://www.reddit.com/r/Daytrading/comments/1ifnvlp/day\_trading\_may\_not\_be\_sustainable\_in\_the\_long\_run/](https://www.reddit.com/r/Daytrading/comments/1ifnvlp/day_trading_may_not_be_sustainable_in_the_long_run/)  
2. Insights | Breaking Alpha, accessed on June 13, 2026, [https://breakingalpha.io/insights.html](https://breakingalpha.io/insights.html)  
3. Does the market move completely randomly? : r/Daytrading \- Reddit, accessed on June 13, 2026, [https://www.reddit.com/r/Daytrading/comments/1izh7ye/does\_the\_market\_move\_completely\_randomly/](https://www.reddit.com/r/Daytrading/comments/1izh7ye/does_the_market_move_completely_randomly/)  
4. Where does the quant "hype" come from \- Reddit, accessed on June 13, 2026, [https://www.reddit.com/r/quant/comments/1nj8vtm/where\_does\_the\_quant\_hype\_come\_from/](https://www.reddit.com/r/quant/comments/1nj8vtm/where_does_the_quant_hype_come_from/)  
5. QuantConnect Review: Best Platform for Algo Trading? \- LuxAlgo, accessed on June 13, 2026, [https://www.luxalgo.com/blog/quantconnect-review-best-platform-for-algo-trading-2/](https://www.luxalgo.com/blog/quantconnect-review-best-platform-for-algo-trading-2/)  
6. How To: Monte Carlo Simulation \- YouTube, accessed on June 13, 2026, [https://www.youtube.com/watch?v=jGhk-uSrtII](https://www.youtube.com/watch?v=jGhk-uSrtII)  
7. Read Customer Service Reviews of quantpad.ai \- Trustpilot, accessed on June 13, 2026, [https://www.trustpilot.com/review/quantpad.ai](https://www.trustpilot.com/review/quantpad.ai)  
8. Feature: OpenHands Coding Agent Skill — Model-Agnostic Sandboxed Code Agent Delegation · Issue \#477 · NousResearch/hermes-agent \- GitHub, accessed on June 13, 2026, [https://github.com/NousResearch/hermes-agent/issues/477](https://github.com/NousResearch/hermes-agent/issues/477)  
9. Quant Trading Data: Cut Costs & Boost Speed | EPAM SolutionsHub, accessed on June 13, 2026, [https://solutionshub.epam.com/blog/post/quant-trading](https://solutionshub.epam.com/blog/post/quant-trading)  
10. OpenHands \+ Daytona, accessed on June 13, 2026, [https://openhands.daytona.io/](https://openhands.daytona.io/)  
11. HierFinRAG—Hierarchical Multimodal RAG for Financial Document Understanding \- MDPI, accessed on June 13, 2026, [https://www.mdpi.com/2227-9709/13/2/30](https://www.mdpi.com/2227-9709/13/2/30)  
12. Quantitative Trading IT Infrastructure: Expert Support for Historical Data and Backtesting in China | Brocent, accessed on June 13, 2026, [https://www.brocent.com/blog/posts/quantitative-trading-system-historical-data-collection-regression-processing-tec](https://www.brocent.com/blog/posts/quantitative-trading-system-historical-data-collection-regression-processing-tec)  
13. KX (kdb) vs Clickhouse Compared, accessed on June 13, 2026, [https://kx.com/compare/kx-vs-clickhouse/](https://kx.com/compare/kx-vs-clickhouse/)  
14. ApsaraDB for ClickHouse: Distributed Real-Time Analytical Column Database Service, accessed on June 13, 2026, [https://www.alibabacloud.com/en/product/clickhouse?\_p\_lc=1](https://www.alibabacloud.com/en/product/clickhouse?_p_lc=1)  
15. Kilo Code: AI Coding Agent, Copilot, and Autocomplete \- Visual Studio Marketplace, accessed on June 13, 2026, [https://marketplace.visualstudio.com/items?itemName=kilocode.Kilo-Code](https://marketplace.visualstudio.com/items?itemName=kilocode.Kilo-Code)  
16. How to Build and Backtest Systematic Trading Strategies with AWS Batch and Airflow, accessed on June 13, 2026, [https://aws.amazon.com/blogs/industries/how-to-build-and-backtest-systematic-trading-strategies-on-aws-with-aws-batch-and-airflow/](https://aws.amazon.com/blogs/industries/how-to-build-and-backtest-systematic-trading-strategies-on-aws-with-aws-batch-and-airflow/)  
17. How To Use FinceptTerminal: The Free Bloomberg Alternative for Finance Professionals in 2026 | Tosea.ai, accessed on June 13, 2026, [https://tosea.ai/blog/fincept-terminal-free-bloomberg-alternative-2026](https://tosea.ai/blog/fincept-terminal-free-bloomberg-alternative-2026)  
18. Selecting the Right Market Data Sources for Algorithmic Trading \- QuantVPS, accessed on June 13, 2026, [https://www.quantvps.com/blog/market-data-sources-for-algorithmic-trading](https://www.quantvps.com/blog/market-data-sources-for-algorithmic-trading)  
19. Polygon. io, Intrinio, Alpaca, or Xignite : r/quant \- Reddit, accessed on June 13, 2026, [https://www.reddit.com/r/quant/comments/1fjbzlv/polygon\_io\_intrinio\_alpaca\_or\_xignite/](https://www.reddit.com/r/quant/comments/1fjbzlv/polygon_io_intrinio_alpaca_or_xignite/)  
20. I Coded Powell Trades' Strategy | Pt. 1 \- YouTube, accessed on June 13, 2026, [https://www.youtube.com/watch?v=u8zyK0p3Jek](https://www.youtube.com/watch?v=u8zyK0p3Jek)  
21. AI in Stock Trading 2025 \- Revolutionizing Fintech \- Rapid Innovation, accessed on June 13, 2026, [https://www.rapidinnovation.io/post/ai-in-stock-trading](https://www.rapidinnovation.io/post/ai-in-stock-trading)  
22. deltatrend \- GitHub Gist, accessed on June 13, 2026, [https://gist.github.com/deltatrend](https://gist.github.com/deltatrend)  
23. RP Profits' 8AM ORB strategy, implemented in PineScript · GitHub, accessed on June 13, 2026, [https://gist.github.com/deltatrend/ec550d13ea6246f25e41023e77426247](https://gist.github.com/deltatrend/ec550d13ea6246f25e41023e77426247)  
24. stop trading like an idiot. \- YouTube, accessed on June 13, 2026, [https://www.youtube.com/watch?v=BiTqwX-4rNw](https://www.youtube.com/watch?v=BiTqwX-4rNw)  
25. I made a profitable strategy but i cant execute it.. : r/Daytrading \- Reddit, accessed on June 13, 2026, [https://www.reddit.com/r/Daytrading/comments/1r7ga0v/i\_made\_a\_profitable\_strategy\_but\_i\_cant\_execute\_it/](https://www.reddit.com/r/Daytrading/comments/1r7ga0v/i_made_a_profitable_strategy_but_i_cant_execute_it/)  
26. Introducing the OpenHands Index | Jan 29, 2026, accessed on June 13, 2026, [https://all-hands.dev/blog/introducing-the-openhands-index](https://all-hands.dev/blog/introducing-the-openhands-index)  
27. Kilo Code download | SourceForge.net, accessed on June 13, 2026, [https://sourceforge.net/projects/kilo-code.mirror/](https://sourceforge.net/projects/kilo-code.mirror/)  
28. Kilo – Open Source AI Coding Agent in IDE, CLI and Cloud, accessed on June 13, 2026, [https://kilo.ai/](https://kilo.ai/)  
29. kilocode-legacy/AGENTS.md at main · Kilo-Org/kilocode-legacy ..., accessed on June 13, 2026, [https://github.com/Kilo-Org/kilocode-legacy/blob/main/AGENTS.md](https://github.com/Kilo-Org/kilocode-legacy/blob/main/AGENTS.md)  
30. Kilo Code: AI Coding Agent, Copilot, and Autocomplete \- Open VSX Registry, accessed on June 13, 2026, [https://open-vsx.org/extension/kilocode/kilo-code/reviews](https://open-vsx.org/extension/kilocode/kilo-code/reviews)  
31. An Auditable LLM-RAG Architecture for Financial Document Intelligence and Decision Support \- MDPI, accessed on June 13, 2026, [https://www.mdpi.com/1999-5903/18/6/284](https://www.mdpi.com/1999-5903/18/6/284)  
32. Issues · Kilo-Org/kilocode-legacy \- GitHub, accessed on June 13, 2026, [https://github.com/Kilo-Org/kilocode-legacy/issues](https://github.com/Kilo-Org/kilocode-legacy/issues)  
33. Data vendor recommendation for US equities : r/algotrading \- Reddit, accessed on June 13, 2026, [https://www.reddit.com/r/algotrading/comments/1smdaah/data\_vendor\_recommendation\_for\_us\_equities/](https://www.reddit.com/r/algotrading/comments/1smdaah/data_vendor_recommendation_for_us_equities/)  
34. I would like to get some statistics for a project. What data provider do you use? : r/algotrading \- Reddit, accessed on June 13, 2026, [https://www.reddit.com/r/algotrading/comments/1m9v5rc/i\_would\_like\_to\_get\_some\_statistics\_for\_a\_project/](https://www.reddit.com/r/algotrading/comments/1m9v5rc/i_would_like_to_get_some_statistics_for_a_project/)  
35. MimirRAG: A Multi-Agent RAG Framework for Financial Data Retrieval with Metadata Integration \- arXiv, accessed on June 13, 2026, [https://arxiv.org/html/2605.25030v1](https://arxiv.org/html/2605.25030v1)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGkAAAAUCAYAAACOPhMlAAAEvUlEQVR4Xu2Ya4hVVRTHVzpqDwlCBXuDhYQvxugFPYYkSox0fILPmeiLYFFfekGPKRLSFLSHUlaOioqKZkhRFDFUENQH/WAQQdCXvkRRYJFkqes3e6171+zOPXNnZGCM84cf956195yz715rr7XOiFSqVKnS/03tyoTcWGl4qdRJrcrtxiXKRcptyo1xkmmcMl+5Mx8YhEYq90vxc1yXKg8odxsX9B2u6TJlnqR1NZrjWmS8pxxS9kvJ5kjaiwPGQUl/x56ts+8O92KcebuVx5TxRjNiHQ3X/pJyxvhX+Uc5qtwQJ0la2DFlhbJM+cLAPhCtMg4rq5WvlJ+UmwwXz+d5K5UlRk82Z4rBvE5Jm98jaWP7EwHwpfKH8mQ2FvWa8quBMy6UtJkEGc/xvXtKGW1MUj5VvjeukHKxh125MQonvWrwoNmSFpKLhxIdrjXG18HWn0Ypvxizgv0H5RtjhNmOKE/UZiQ9KCmAXMyBuMkdyrfhukwEytuSNrIoitnc55WfjV19h2Wy1J30cDZ2axjjZJWJvb8mN0a9KCkiGkXfVQYPw4GuewzsVwZ7mUiXnFTYEeybpP6DpisTldPK3DAHkc6YQ6SSovxeCwrmcBLzbJALJ/lpuDcbQwTttdKckwjYqLYw9nQ2FkXgkuqK5AErL0jK+/CIJK+yCS5+tP9wosN1s4EdZzUrNhdagm2f1E9YTCP80CgciB3nxVRDvXJNNRu1E8qEkxCnkzXket0+B+ok9o+swD2B1NpIpGhKSK61yrN+8ZzSbXCz65XjykIb90LLQmI9mGlgXxrsA9V1yinlcQMRMNz3Dp9kov5g71Tm2He4K8zh9GB7yCiTO4na+Lf0LfScLD+hzTjpM2WzpBpGeqM83GKUaa9ycbimkQLqZU2Vk84DJ9Fyk/tq+U9SjfAC3W6wENKbKzoJh26U9Hdl5MWZfEx315XZqX3cN2/13UnLJW2ib1BbmONOoiuEMr1vn7Twf0pqVLxZYb2sDzXjpLwmEdDUVfDgy3W58lZmI6V7Wv/QjXRMdBaxu3hG0iRu4u9QXPPp8majaDObEUFBweywa6IJaGGJJO4bO0DUanYcNMO+Q6yJbmdOUTMQ5U5CNDLfGZymrjA2GCchTgP8JcVtOI1Jo4aNtfc6iT/kAV2G62VJ70y83I41eJCnQORp8KSND1RbpG+3yMsh0EnyCvCbpPepqPskpUYif4zyuxELLz+OOTF1NRLtuys2IqTB2DwN1km8CsAJSZ1trvh8l7+4xxTeG03cwG/CESfV0eVFbZO0sa43jDeDrRn5OxnPIHcDJ+pHw1Mi6eZd++7CibF193t1B9srys5w3UgEKKfm6mDzTaWeRPnLLPUjaprUnfRosBNkdGc+lr9DecdclAYJOKDGEYy9Ij1sN9gUjud6SZEaxYP58b6xWw1a5mbFhngKyGHzowNIh6xpj6QIhnekXid8DrBun8f3OCeXZ4CPlY/s008s/0kBP+GUAqKdOT6foGbPCA420tf/uc35QPlE0kuyNwG5qENQlAIXGxskHYz/iJqQF/dcbEpLbhxC8TzqFJTJ5w13scce6INS5aSh1zk7qdLQi9TqKbfSMBXNBzWzrG7WdBbNo1ir9XnNMwAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADQAAAAUCAYAAADC1B7dAAAAmUlEQVR4XmNgGAWjYBSMgpEAnIBYCV1wKAMRIG4E4llQbIsqPXQBFxTnAvFyII4EYhYUFUMYMAJxKBCvBOICBoRnhywYdh5CBnZAvBCKW4GYDVV6aAEmII5hgMQUCGdBxYYc4AHiUiBeCsQhDBBPDDmPSEFxJwOk+LZGlR46QAuIpwBxHxQP+UrWAIiF0QWHMhh2HhoFgxUAAG7IEK9a6LFdAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAYCAYAAACWTY9zAAACP0lEQVR4Xu2WT0hVQRTGT1IhEUH0ByutUChoEREYRrQtFWoRQgSpiBImRpKotBAsEqk2IW5qIRZoFC6iCKJF1Epo08KVbt2Eu9qVUH0f8033vHnvYouEt3g/+MGdM3Pvmzn33JlnVqE8uCKH4K6kz9OXBjaa/zaxOnhARnh9yLUj1bAJ7ks7xDi8JRvgCrwP97sxx+EreMPFSjIBf8tV+NXCA0/4QaAefoaD8A58KXe6Mbx3tyRTsBkOWJg0HYHv4CaNyYUTey2fwZuWPdjzHva69iP5RG1OnItjVikZtZA5zww8mMRKwlWcknnwQb/gGRfrlN/hZrgVrllhxuZhla5j7V1Xe13uWTYx1s9VuKVghNl5C9k46mIXJeNHFJuxkFXK2p1VnDX5XP4zZTuxu5bVGAu1Gy7AY25Mh4UJ+HpplYyfVowLYl1R1t8exedgrSTcRk7qOhd+vhzo9xyulPUR6bHiibVIxs+6eArv7XJtjmXmhuGYixex10KBxiIlD+A3Cxmg6SsjFyTjPrse/zojH2Cjrt/6Dk+NhS/ptow8tPCD2yWzyjZrMNIuf8AdLu55YdlmvE3+tGy7GLOcRfEz/2Kh0w94Az+6NlmyMJFI3DA5thT9FraHSMw+E3FYMZ4Q/lT4S9lOjLAIeZ5RFia/qGUr3rH5GhfhOXjJwvFE03OT99HpJB75BC/retJ3lCI+jGcaV5lXMyzmaxa+Mr/Dex7LvH8WfAaPt6ewLenbUHg4r3tAW+EuUKFCBfIHDGV2DGTP3NkAAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAYCAYAAACWTY9zAAACGElEQVR4Xu2WT0gVURTGT6GSLgRRF4VJKiS0cBEIhrTtH1gQgghaBBEmBqJYC1F04aJdRAS1CF2YKC4CCUJUcOu2VesIWrcpDazv836XOe++97Qi4S3eD34wc+7Mm3PvnDn3mZUpDfrlBKxPxjzDaeC4+W+JXYOt8ihOwS54Oh0Qc3BMtsHP8Ck8467pgO/gIxcryAb8JffhHtyFP+CiJEx8B47DWbgi6zROvsIGSV5YmPiohaTpE/gBntA1ReHD4k3TcFJ+sTBrStbhkI7JM/la50yck+OqUjJl2f2RedicxPKogS/TIHhsoU4iLRZWs9vF7spvsAJWwZ+Wu2Kr8KSOY+091Plfc9GyVYhctbAa7S52UzJ+XrF5C6tKz1pWBqzJJfnPlGxirDn+qOeOhQR8vdyQjF9SrNJCXVHWX6Pib2GTJGwjXIA/5hbcTIPgvuUndl0yftnFU3jvPXfOa7lyrOMZFz8UJvU8DVr+KyM9kvELLu7xrzOyBTt1/N4PFIKvgH630HNS2BSZAJtrZFCy59W6uGfZsmbMDkDZJ2O7mLHikzqAD6R8OJe+EJ8sJBKJvW/NxTwjltty4uTZUs4pxh3C7wp5lGxiVyQTG0jGIkz8o4Xrblv4emm6b8bd4k0Sj2zDPh0XquccqiVnyTooBov5gYWvzHd4zytZ7J8Ff4Pb2wLsTcaOFW7OR27Qlm1VZcqUifwGN+tvw8igPF4AAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAYCAYAAACWTY9zAAACMUlEQVR4Xu2WT0hVQRSHj6ESLoQwocQiEgwiRIKgjHaiFeRCBHFhIYSoKImhrQIjWrQIQiSwIHShkrRIRJAWqVtXUSvbtmkpgf9B+/2Yc949b3yPLFDe4n3wwZ0z982de+6ZmSeSJzdoUwdhWdTn6YkDR82RTOwWrIIFcYdyEl6HZ+MO5QUcUDnOT/gSVrh7auAn2OdiGamFE2ovnITf4Cl/E7gIV+Bj+AzOqP6+X/C0SkbhbdgvYdL0CVyQ7C+fYg7OqoQP2pTwVp7PsMu1X6tvtc2J70vIKiVPJWTOMw7PR7GMvILvVFIEtyVkzuBAe/Cmiz1Qf8NCWAx3JT1jH+EJvbba69b2P8Mfb0moN6NRQjYuuViTyni1xsYlZJWek+TlWJPT6n+TUxPjAqBM/QasS++W+xIm4Ovlrsr4DY2xDFhXlPVXrvEpWKkSbiNX9fpQcKVwFf2A9S7+UA5O7I7KuM9uDH/b4dq8l5kbgsMufigWJexBnCiNPxm5pzJ+2cU9/nMaX+A1vZ73HZ4zcAm2qgYH4wPtE1/RNjdXo13lCi51cc8HSTbjEnVHku1iWLK8FNPKBz5Xja9wTULNULIqYSKGbZjcBzPBzZoLybCxuKVc0BhPCH8qpMjZiZE3khxJLPhHcF3CIvDwM36HDbBZwvFE43OTC4S+j+LGsiRlM+I7MsGHUp5pLXLwnDRYzJ0SVpnf4T1jarZ/FhyDxxsTwWcdG7aS/4YdVXny5DH+AEigeQ+y+2VSAAAAAElFTkSuQmCC>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACYAAAAaCAYAAADbhS54AAAB8ElEQVR4Xu2WTSilYRTHjyTDQilqTKEQmoWvpiglK1n5WMkGWY0mkd3UKLNQs5iVz8VMuhYWRNjJQnaKnY1SLJGGLGyk8P/fc97u47myudN738X91a/uc87z3s59Ps57RTJkyPAmFTDPJDkwN5EOn164B//CI/M33IaVzrxQ6REtqsCLL8ELLxYq57DTD4rGVvxgGJSaz3DYy5HPsMsPhkFkC8s27+ADjMF+WGimHd7If6IrR1kobXAnpYsPsB3OwCdzzZ0QFrWw3vTZMnds/EX0hrKdBOey1XI+nDMA6/wEKBPNtcg7vfG7aP+iPmyqdNLGP+AjXBYtkP6B65LofUMm43x7zMJpyxFeIn5PuWgTH3Ryr4hsYbtww3ThgWfDpUVOnJehyRmTU9Gt4fv00vxkOd72a9Fto79EC+IWlkjyd8XhQ2eiv5huwq+iq3goWpx/I29hoxfjW2FVdNWvTJdjOGHmw33RW38gya+/OAxWO+Nm0QbbAbOcuMuNJBd2AudFGzG3mrr/RPhj+szgyHyEi3AhmJQqLGzEGbfBe1hjY95g2m1jnkOuWNDEubps3kFu3D6nDAvjdo+ZMVjlTjBG4RycEt2+ABbC53/Cb14uJbgt/rmLBJEsjFvHg83eVGxGAvYcrhZvJc/GfzsfLi8QiGorL+Ma6AAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACsAAAAZCAYAAACo79dmAAACK0lEQVR4Xu2VS4jOURiHX6QklKRcYmElpWahKBGymI1iJRIbCwtFkUuor6SocSlW0yzGQrJTSkkuJTZKs5mYiUlNs5EUQrn/ns57zDvHf+b7mg1f/Z966ty+9zuX95y/Wc2/Zaac6v73tM1kmehrucaNdMqjTTzs7pfT5W550b3gdsmzcpePmTQN+UtudSOvZLfc7jL553LYy3jC/SKnyUXygKWY+9yVcq08JUfkZpsES2WfpcB73cxqeTnUgTR5L3uKdngYyg35Tc5xIy/k46KtJa7LVZYmy6oxc0YuC3UgTRi7I7TlXL8W2h5Y9YRIgY/yUdnRDI6iYemPfshLbqYjlDPkKJPlqDMcPXLUMMNSSrDYyBR5Wr6z6tgT0jaTJfgtS4HhjaVjjEdZxR05WDYWrLe0oKvyoHtSPpW9csGfkS1CgG2hzg0nz7AKFoWfLL0OE0Hef7W008vdLfK73BPGNWW+y9NzT951P8h+t4p1bnm5qhjvct20tCktw5ODK4r2G/KtWwXHiGW+lnDbP9vf+QrP5MuycTx4wPMXpeSK/OlWfWFyigyUHQWbLC2I/4oQk3eXvAU2iy8njoGc4TIR5Im7xPu4occsHT/9eM7S28sbe8jSDSbfkJ05LnfyY2eue0Tet9EYpE1kyNJiF8rbNvqKjKGtJkuObXR5W3FW6Ke+IUidxSz2Mr/LfRwzbSwmM9uljzFIOW9IhnhszHk5r+irqampaVd+A8Z0lAMzrwz8AAAAAElFTkSuQmCC>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADoAAAAaCAYAAADmF08eAAACk0lEQVR4Xu2XS6hNURjHP69c8kiMiMJEiuQRJUREyTMThXIzuAbqjjBRp1BEkteE5JFEBh4TpEzuQAwYUCYykFzSjYHk7f9rfctZezvHuZOddnf/6tc561v7nLO/vb9vrX3MKioqKir+L6flQ/lMdsl7/oon5aT6oeWnJr/LEbn4Bo+vy8VLC3eRu5qnn/wmb+UnysgA+UkeyE+IefKX3JOfKCN9JtH5FpJZnsRmuJTzddmWzKXslVcsHNsbZsrz8mAS2yIv+Wuh7JY/5UV5xkK/vnZXJcc1Yox8JRfnJ5rQX3bKB0lsqLwm9yWxQrgtHyVjrjoLEG5L4s1gW+ptorDGsonCcSswUcoR6c+0lOCxeycXj0yQCyysyk+tcaIr5Eqr/05ktf2d6DHLJjrdpZxpCyoBuPtIuy2SY/39P1no0p+cVGSI/OLeTOKw06Vvl8gO+cGyiU6Wd+UcuUw+cSlzaJUo3/XeHW9hj6eHYZx7Wb6V+2WPhUWzKX0m0Zr7Q45K4pQKyeM5j22UU+Rnd5jH4aVlE6XfuBgRTgbP+rhVolyQTW6E9YILGJll4fwmWjivQcncHzgpVrl41b7KG1avdR4Dn7tsL/zgYblVdrsp+UTfWbZCdrgvfNwqUfoxfobfrVl4DJ3q88CC+SYZN2SgHG7hrkRHejzCGNle1nqMxeejm0KilHGkS25Pxofc+z5uleguC8fiYI/RRrQCiyCSKNtaYdB7GO8YZc6qnZYZK+VVfz/a6is4FwrafdzmcgcvWPinBPQf/6gQ+Fzc6mJJL7VQOXy+EOgfpAd50CBhFgoSI+n4hDTbQq/Sl2l8rjzh1tzNfiwx/i1xcY66zLPvrpdH5DT3lB/PKwtWRUVFyfgNPRGsFUgWFSkAAAAASUVORK5CYII=>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAA+CAYAAACWTEfwAAAFKElEQVR4Xu3dW8hmVRkH8NVJJcoaS8gOFJ7IsSLHoswKE08IKmQIigeKCIPSyNSIREG6CPTG6ECFjFaKIoIKohkyF6IXQUGYBlGCJULn6EJCoZ4/a+++Ndt3vgYdv5lxfj/48+797PcdZubqYe11aA0AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACANT+o/HDK9yrfqGze7hsAAOxW76r8vXJP5cjKaZVfjV8AAGD3uqjyn8phQ+3blfcP9wAA7EZbK38Y7o+v/HW4j7dWPr+ojU6sfKn1355fuXz7xwAAvBhp1h6vfK1ye+Xh1huw0Zsq1y5qo/dVflm5rHJq5ZntHwMA8GKMr0NPmu5PXnvcDqzsV/nIUIv3Ts9mP269YYs/DvU3V1453L+hsqlywFADAGAd4+vQi1tv2DJKFmmqbmr9Ned35i+1/urz7Mqtrf8mVjVsX6zcW3mw8rGp9mTlkdb/3P2nGgAA6/jRcH1j6w3bhysfqlw1PDt9uP799PnattbwrWrYPlm5sHJm5ddT7auVP7X+WwCADfWpyrbpOg3PX9Ye7ZG2VI6bcuxQP6fyzen6/qGe16XxwcpzQ/130+eqhi1z4rLP2wmtN3YHVa5sfXQNAGBDZZ7WvyoHD7W8LtzbpfGcXTpc/2b6PLTyt+n6lspXpuunK69qvbE7pfXfPtX6StKMsGnYAIANd17rrxJvq7xmqplUDwCwB8lqyWxrkabtn60f77Srfbby9XUCAMD/kRG1rKb8c+uNWybc70rZvDZHR405onJ42/6UAgAAVhj3GYtMsD+j8vPW57ZlMn6u54n7n2h9Yn/O7/zAVMuo3BdaP8tzlWyj8bl1AgDADmRy/ceH+7Mqv239NWlOAHh2qudszly/sfUVpBkxO6b15i5bXMyN2rxf2VJ+/9F1AgDADmQT2WwEmxGwrBZ9rPKe6dlRlX9P1/FE6xvN/nSo5XmatRzn9OhQBwBgA6Rhm0fYMvKW60NaP1w9I3A5szPneGaULud1xpenz73VuAAi24LcvCLZ1iP7s2XUMHu9pYHNZ05FyCkLr8iPAQA2wtyw5cSAbW1tX7M0Kt9vfa+27GUWaWDyvYzS7a0uqHxruJ8btHe0PkcvizHyKjj//l8M37u79XmAOarqvtZX3M7bowAAvKSyavS5ZXEPlpWtaa5G2U5kZ46RyiKKNKTbpvuMKJ77v6d9VHHcTHjr9Jn/o3cP9Rta/z9LUwcA8JLLzv6XtP7Kc3fK69drWh/l2q/1V46Xj1+Y5Oiou1rfKmS2MytQN7c+QhiZwxebKq+ertN8ZXRtPig+3jJ95vzSUU5OuGJRAwB42Xuo9XliWZGaszyzyCEjZ6ukact2I3H1+GAdd7S1Y7nmo6pGaVzTsK3aLy4HyX+39cYtf08jawDAPmc5Jy6jbNcuaqs8XDl6WVwhr0sfrPys8kDrjVkWVoz+UfnJohafaf37s7xSzeHzAAD7tE+35zdUS9dXXl+5c/lghWXzlwZsOUqW2qoRvSxIyEHxszRwu/qECACAvc582sKOXNf6as94XVt/lC1/Vg68H6U5y9Ycy9qq16FPVW4Z7rPg4ITW5/ydMtQBAPYpW5eFF+jtrW/RMa4qzf1cyzYd76y8bajlfpZXtann+SgLE7YsagAA+5Rs1AsAwB4qo1rL+WUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA7Iz/ApqYwjYvxYnwAAAAAElFTkSuQmCC>

[image10]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAZCAYAAAAFbs/PAAAAh0lEQVR4XmNgGAWDCXACcQEUbwRiCyQ5ESh2QhIjTQMrEF8B4ktQfBqIfwOxBlS+GYqVoXyGRiCOhHGgIAqIO4GYC4iXQjEcGCBzkADIaVlA7AHFBMFKIN4JxIxQTBCAnJSPLogPTAJiYXRBfIBkDSD3Ew1AYQ4KJaJBDAOJHgaFOyg5DEsAAPk8FVPs91f+AAAAAElFTkSuQmCC>

[image11]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD0AAAAYCAYAAABJA/VsAAACvElEQVR4Xu2XS8hNURSAF/LMI2FiIFEyEQMZEBkYmMiAklceyVtIGImSYmDgkTwilKIMyMCAjLwSilIiDGRABkIYYX3ttbTu/u8+9zCQ3PvVN9jr7M65a5991tpXpEOHDu3AuDwQ6KlOUYeaf0q8T4mB5lS1f3Yt4nP6mrXg4fvMx+qtxsu/mKA+UDepe8xzap84qQbc5766Tt0r6R7YO8yZrj40V6uH1MNqtzAH5qq31SXqKZPf1ZIZkh6CF6WcNAnPz2LnpeZDAo/UOWHMM3Gnjburr9XJpnNTXRHGvP1P6igbsyD4Qp3tk+pwVponzdv5oY7N4jvUp1msiomS7jM6xEgW/T6zJM3pZzrH1ethzA4g6ZzLknZObUpJ84b5IcOy+CqL813VYZGk+YNDjG2OxPnWt6tfw3WHHfU+jA+qr8LYOSm/9yI6SUc2StcfC8stPiKLl9giaf6AEFtpEh+u7pfm23aX+j2M2cLPw9g5qr7Ng1WUkvYfW0rai0kreItVSbN4B6SctO8GvCDlpOOOaAlJ0wJylkp6YN5XqabNFqPEMknzB4XYGpM4hYvi+CVcd3arH8L4iPoyjJ0T6rM8WAVJ382Dkpo/Pyqv3lvl91bV7xN3BkkibQq8fuSHDb5h+rbDeeFjGDu0vyt5sIpS0vBOuvY/DgPHwnibSTtpBj2Y+8wMsdMmSQFF8Zs63nSuSVoch4VjcfLi+kQa+3lL2ibpeZKOefhG/ayeUdfGSZJObvfUaZJaD96RxnbFMRZpOb1CPELC3IetTiGkcGKsC4vVG+YkdbN6VRqPqsACX5J0eKKlIVWdxa2ENsEJCUearGKzNsQ3vV5daOb92b9DisyQ7FpkjKTevEBSJY/V3PE3zbfLsbV0xmdRmMNJDns0Xv57UODahg1m1d/T/w7/D9xWtGXSHf5FfgJSx7FOojyEEAAAAABJRU5ErkJggg==>

[image12]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAAA3UlEQVR4Xu3SsQtBURTH8WNQlNEgxcogZVNKkmL1L8hgN7CxKAp/gUnZLBZ/hkHJZrEZlU3xO93jvtvtvRe9Sb1vfQrnvlMuRGFmETGBBSwNc5hBB2LCszzs4QolUYAKbOEiEp8H3DrB2v6Q1PKX6FszXZLUga49QC1yFvSsmS7wgjapAzl7gHZwFlFrpuMbv5P6vryEVWEDK8gIzw5whDGMxBCyxhnX+GdhT1IP/FzgBU3BF1i2Zl81FQ/yuWG3ijAg9ddlN3mfMg/5lYY61AS/bkDcOeJf4AVhf98bhRQue0EGKZ4AAAAASUVORK5CYII=>

[image13]: <data:image/png;base64,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>

[image14]: <data:image/png;base64,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>

[image15]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAYCAYAAADOMhxqAAAAtElEQVR4XmNgGAWDDUgA8RR0QSAIAWI1dEEQKADiW2hiXED8HYht0cTBYDMQz0YTcwHin0DMiSbOwATE74E4Ek28FYiPoomBAckaTIH4PxBLoYmfAOI2BohfWJElyoH4NwPEJhCQg+I/QOwBxI1QPhzsYoDYkMEA8egmKL4HxGUMaIHBDMQfgTiPAeIHULizIWEQnweuGgisGSCmgyKOKFAKxDfQBfGBOCAOQxfEB0jWMMgAADg5HekHrGv6AAAAAElFTkSuQmCC>

[image16]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAwAAAAYCAYAAADOMhxqAAAAj0lEQVR4XmNgGAWDEXgAcTsQ90JxPxR3ATEbkjoGLiBeA8RvgHgDEL+F4idAPA2IG4CYEaYYBOYA8WoGiEYQiINikAYMoAXE/4FYFkksBIpBtmAAkjVkAPElNLGFULwLTRwMvIH4ABIfZNNXKDZAEocDFiA+D8RhQBzLAAklUPCCMF7gAsRRQMyKLjEKaA4Ak4gcR2J7c5MAAAAASUVORK5CYII=>

[image17]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAYCAYAAAAs7gcTAAAAhElEQVR4XmNgGAX0AkxAPBWIlwNxJpocCGQAsQGMwwjE+kD8C4iTYIJQYAvEf4BYCVlQG4j/owsCwREgXokmBrbqMZqYHxC/AWJlNHHSFIM8twzKloXiG0DsAFOADF4wQEy3AOJ9UGyJogIKQNaAPAcyvQGIeaAYKxAEYmsGSHiPAtoAAK96FbvJNmdFAAAAAElFTkSuQmCC>

[image18]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAaCAYAAAC+aNwHAAAA2klEQVR4Xu3SPQ4BQRjG8ddHqREqiYYLKFXuoFRQqCQaDZVGoVOIOACFAyi4gk4hcQKJCnEDnjf77OzuJCM2W0n8k18zM3l3MxmRf65S0IMdHWALNajSyJy2qsMJllAmrQJ7uFCX6yadrp7Qtvb8mvAiHWgqwpVW4Q2rvATnIiUeMJXg1/QOXGVgTJEecCM9FKuSeF/eUOz05nVAnz41tBe0xANy4t3Bmlw1oGUv+g3gTllrT9N7WtiL4fTmj3QW75nqe+/QBArmtKM06TOew0yC5/1ViQf8+9neQTwxjmoRuosAAAAASUVORK5CYII=>

[image19]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAbCAYAAABMU775AAAAuElEQVR4Xu3Rvw7BUBSA8UYwWG0iRpPBYLMKr8Is/iwmERNv0d0TWA02sXoEVokIvpOcJjfnVnJ1E77klzbn9rZpG0W/VwkrLLFQct53L0orhwZO2KsWKu5F7yrghrEKLvPGNp56FMGNcEVRBbfB1g5DyrzxgrkdannlJf9QPkzPLlANE+U1wANlu0Br1JVXjKMdUhc7O3T7aGMTM3XGAUNnJje7Y5psSKqio+SjWPI0WUt7739f3gt21yRLE8+1RAAAAABJRU5ErkJggg==>

[image20]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAZCAYAAAA8CX6UAAAA+UlEQVR4Xu3SvWoCQRSG4aOQQgsRbLRI6iAWChYBm0D+rHMBYmFnYyNKSLFNSBOxT5eLMEXqQG4hjTZilyZgp6jf5Hy7LLM7CsFyX3iaPevszKBI0n96hHHIiF7Ag9PgzQOdwRusoAEVqsEzLKATvH2gD/i0H7IWbKBIztLwC0/2gOVFd9smZxewhWt7wDKiO3olZ0dbqC+69Zw9YFXRD5mju47/10TcF23qiS50SZHMJRtL2f+lL/iGFEUyd+PfT9Oa+d2LHrtuD8I90Bqyoecn1IW56GKxlWEIU/qBAXkwo3c415/Ed7SFSqL/mbuQW7iBKyhQUpKrHWvLOFP96RSuAAAAAElFTkSuQmCC>

[image21]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAaCAYAAABozQZiAAAAyUlEQVR4XmNgGLnABYjLCeAyIC6EYluINgi4AcTToTgYiN2B+DsUb2OAGO4PxHuguBWijYFBC4inwDhQoATE/6E4Bkk8DIqTYAIgJ6nDpSEglgGhWRZJPBOKrWECFGnWRcjBwSwgfgTFyEANijnQxFHALSBeDsUkAQkGiHNhTiQJhDNANOtAMUmAIs1TgfgNEDNCMUngPBBvRBfEBWSAuBiIO6AY5ORTDIg0bYdQignEGSBp1xGKHYDYCSoGwqCkihNQpHkUDAkAAPOAL+l8dYL8AAAAAElFTkSuQmCC>

[image22]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC0AAAAaCAYAAAAjZdWPAAACNklEQVR4Xu2Wy0tVYRTFVxkYUUFYYEEOCqIEJaQQkV7aQIqeBGJFg1BIEnwRPShwIvSgiYED/QOaNOhBYg8EaRA4yJEQQRlEMwc20UFGrsXex/v1eWug0j0X7oIf95y9P87d55y19/mAggoqqKCV0iAZIxPkPXkdMEpaSfHC6hSpl8yRTVG8nPwgd6N4KvQW9rSz6R2ZiYO5VhGZJffiBLWRTJM3cSLXysuia8lv0hAnqOswa+yOE7nWHVjRXaSFXCUvnYdkW2ZpejRMPpN65xApcVKntY783B/lQm0hR0gVzP9C55vDRa5KconsJaui3GqYBU+QA1FO65tgVs123QUddGSNxigXaj/so/OdXHHOwT5GZ3zNcWeSbIc1dfwgnsF6o4Z8CuK3Yf+/E/bWq4PcIuVl0T2Oiv7nK6E6yfModoF88WM1qzjv5xqVuq6stcH5Rk6RdbAbTDREbpFSmE2yNr789IRMOb9gT6EuXBSpHbYm1A5YYRXI9Mc12MTRtkC5sICzsJmvHmoO4mXkI2z9Y5j3F2kN7M7XB2jPofjflK1oWeQnrDAVKV7ArqMNVnJDe5zDsCaWJb+SXc5JmGQPbdLa/HzZUtEai8lNqjDN8QHP6xWL+35+DLYB09y/7HxAxoZPYTYR42Sfx7vJUT9etlT0CGwsiT6PJWMt8fQjchNW9EXygGx19BHrITfwpxXViB3+K9vEo3LJ0kVje6ReeVe0xtArmKdPO6mXvKrCRdLx/1XzbJJ2RXn8oDIAAAAASUVORK5CYII=>

[image23]: <data:image/png;base64,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>

[image24]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAE4AAAAaCAYAAAAZtWr8AAADhUlEQVR4Xu2YWahOURTHlzEhJV4IDxTyIErGjEmeyFDK1KVIIVKUzA9KGZIr04OpEFEkkvFThiJDorzQjQjlQUKGsH53r33Putvtu0P3dus6//r1nT2c/e3zP3uvtb9PJFeuXLly5crVMDpm3DNuKdeU68od477RTxml3FUeOC4pHSXTYuOp8lhC/9auvUlps/JH6Zo2qEYon5TuVm6mfDEuxk5ViJcwV5qwaYiHfJJWOrECW7jyc+Ohq4saZ2xNG5qS2hrflVJXX6L0NBDb2euC8T6pb6NcNhi3ySo3ro6aYBDfplldDwnblq0Zt2dz+4w6YHBfK1e/VplsRDHuduWIq6tPrTR4ueOTtpqIpHdI2Z82FBNJAX4rBQnZk0Rw3vWpSqsNjOtldazO4xU9goZIGLebclvCioT6FBkdiLfzkraaiGRHEnuRNhQTRwXwiYFBVrgyKypu2ajZBsaRCNAZCQZ5sQL3JHUNJTJ8XYxDw6UWxhGDfhg7Xf1Ipa8rL5fMnCj6AMYx2ZkS+nl1lmDaYWWAleN9TBTxQhi7t5VRfwnhg/kxj6ESQkUaLjg6cS8vFoi5qXETjbgrohiLcYG2YVIL4xiQB4dJSRuKieNK2iBZ4uBeTGfS/riCMIt6VvQyZbCEYw/csD5TlTJljZXRKuWXBNN5IVuUE0bUHAlj8AzsEHgrmXFdlLMS4isskizGsq2ZE98DY5SDkhtXrgY1LiYFYBt5sQ0wDPj5lCpmXB6Qo8ygys0VWq/sc+UFRjQOkVC8ceiNssSuyXpfDcRcv0nlcIIKkhlHbN2WNZWrTIJpOySEDy+ycbXG0em08lGyGEf5pHJKuap8lpBdodh5jAfclVY6pcbNN6oz7rUy1q77KD8NxPxZ6S2tHFWQzLhHEk4GGBjZJGGXcHLYaP2iamQcKwXnOxWB9nZGMU2X4sZukMrnoxLjpqs7J/8a90oZbdckDm8cK42Vzjy9CpIZx4thZXnx3Pxu5rzHudIL414mdY0q4t9RyeIfWRD41wQRB/mzoNTKqIPyQUL8Q2RhjALaEDFpoV3z5wO8U9ZZHdmSFcS2jmGIeEYIwvhnksVwxO9qvjOO36giKO82CPBenPR5SFYI1wTyGQYrBSNJDiQtPuM4eyUcPdorSyVsuSkGIYOQE389DJRgMBDPMTOKf3yIgUDomCXhHMh35MqVK9d/p78iVOoJmH4qdQAAAABJRU5ErkJggg==>

[image25]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACEAAAAUCAYAAAADU1RxAAAAkElEQVR4XmNgGAWjgDjggi5ADxAIxCuh+CUQX0eVpg/QAGJJKJ7KMECOQAZDzhEcULwRiFPQ5CgCIEfcQBfEAXig+B4Qt6LJUQSGnCNoBkCOuIkuSG9AjiPY0AUoBXOA+D4Qc6FLYAGCUPwOiCehyZEMshgg2QyEd0LxNiCehqwIC2CE4nlAHI4mNwpGAdkAADbYHDKuqkcPAAAAAElFTkSuQmCC>

[image26]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACsAAAAUCAYAAAAUccS4AAAAi0lEQVR4XmNgGAWjYBSMAlIBFxTHoEsMJiAFxK1AvBCKrVGlBwfQAuJpQDwVyh50wBGKFzFAQlMCVXpwgSHhWCcgXgXEBVDMhyo9uIAuEM8G4m4olkaVHpxACYr7gHgWEBugSg9eIAzElUC8gAGSTIYEYAXiFCBeCsWRqNKDG9ihCwxmMKQcOwqIAQAj3BDzC1OUfQAAAABJRU5ErkJggg==>

[image27]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB0AAAAWCAYAAAA8VJfMAAABZ0lEQVR4Xu2UPyiFURjG3yjl36gIKYNMsigji5QYZCaLksRiZzQopRQGsVhMlJDZYjBisCjZFRkUz9P7nOu75x6fzR3u/dWvr/Odc973/DerUglswp0/3JBkAe7DXbgnF1VHGuCBZDt+S2iHx/AN9sJO2QX74Ba8k4RBl+EXnJP1qgvMy2s4GtUVuIeX8U/RDM9kYMA86ayMOZIcfJIW8wAr0f8lfRvhtgy0mvdZlVkmzWPF8YooS9Ip8wCDKvfLk0IL30ea5cP8MNFAk3m/WvkrnAEDcE9v4KdcyzZK8AjPZYA3IQw+Fx6i00x5XQ6r3GE+A5rlCj5IwmRMmkub5NLyCgS4J7ROZV4nXon4WvD+vUsuJZc13oISpiWTcg9TjJnPOgWXn30pH46J4uo0ZUkanqpXWBPVkXH4DLvjCjFjP0m5BbmMwAvzgPRJZb44/N7KF3ioPimGzAdMeTb+BR6sHlmlwvgGJTJhwDVFjNcAAAAASUVORK5CYII=>

[image28]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADcAAAAVCAYAAADiv3Z7AAAAlklEQVR4Xu3RoQrCUBSH8SuCIFhkYWX6ACajeWFlYbAnWDAYBbPRYLAaXBMG21v6iSfsLlnP4XzwS/9bDjcEz/M87/8KZMJcKW6ixSGedWf6uHErXNChwkyYao4GgzhiMX5gqRI9ztNBc0txCr8frONZdyaPS3DFW+TxrLMtHnhiP9lUtsNL3LGJZ919f2gtzGX6OE9bHydcEnfbPjapAAAAAElFTkSuQmCC>

[image29]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAYCAYAAACx4w6bAAACd0lEQVR4Xu2WTahNURTH11MkA6UkH49ESYoMTSgGmMjnhCRK8jWQRJLBq2fkKfkYyYBIjMhAGYiBFMpHmRhIKUWJoW/+/9Z/3bvvds+55/QMXq/zq1/3nn32Pfesvddee5s1NAyX9fA4nCyL2Jk3jHT+a2Br4RxZhT44X9ZlAVyYN4rDcADOgu/kGThN9/m7W3KX2kq5D//IX/A7/Aa/wtOSrDL/o9fwkqzCRHhT8sX3mf/nzKQPeQnn6fspuQYegCfgEXhHcnB78tz8h5RpcEyfb+F0SZgmS+ATqxcYX3C1DFbA28n1JPOBnarrg3Jxq4f/X7/sCR94Nm8Eg9b5IikPrV5gDOCkDJhuHNCUT3Cuvl+XY3W92SquqzKWmY9yEXUDYypFql81nxV+rks7gSF4yPz+DUmmwGtWMf3KGJWB8cfPrLzU1g2Mz7woGdxP657+7McCcd68EkY1vGztdcWlQ9O1V4lN5uW0jLqBsfo9lZy99+YBHk07FbDN2qV9qflMUxY4DkJlHplXxzIYGEeRVuGFedpF6rH88+V+W+fMpEQ1ZgoG98xnKmYrraqFTJBMk17Vh4Fdkb3ghvwmbzSvdh/hSpkTz48U5Ltxb50hCScg3wv/YblkimzJ7uWUBTYg9+h6PPxsHiBNeWVeKGLvCrbCHTLgQPww3yYo4V7L2S9l1AYWa4CB8YTRjb3wHPwCP8gLcGPSh2lH7yZt2+Fjye88dXCN7W53acF1xXvdeAA3SMLtoSexxvbrsxvMZx6UZyfypBBHLhLPGZe0kTg0s8KxMi7qvN0iPfTmcL1xwCgLV9HJaETSlzcUMCZvaGhoaBg2fwG9nJcbsJ3KKgAAAABJRU5ErkJggg==>

[image30]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADYAAAAYCAYAAACx4w6bAAAChElEQVR4Xu2WTYhOURzG/8gUScnQ+FxQdmSpRKPU2GBGSoQSiVIkTPkqYTGhRDZWYyKRjSyUhVjIknyUFE1Z2ynf8TzO8+e8533PeW+NxTTdX/167z333Pfcez6ec81qakZKHzwBO2WOXWnBaOe/vth6uECW2GzlxqqyFM5NC8EReArOhx/kJThL1xfDu3K3yoo8gr/kT/gNfoVf4EVJhqM6vO516GHVycGXoQ/hfjgA+xtqmL2Ai3R8Qa6FB+BZC/Xvy3GqV+S5hRspp8Ex/Q7D2XISfANP69pRyXtYPtnyzIDvpI8UO+v13xpm0yx0WpfOD0p2hnPNwv2tRrsJ/uHltBCcgWuiczbAhlKuWmPjrRiCd6TD6bYkOicf4UId35ITdc5lUGldlVhpYRqU2Co5rdrxFp6Tey2M1rqGGoHz8JCFUbstyUx40ypOvxJj8sV48zMrpx+nLxc67UiupUy3sHbey2UW1uwTaw4cts2AuGIhCT0NOZV9XbFt2m76N7HRQpyW4APFaVmCKccX48NRh+vlE5wqc2y3f9G+At6QDLg0VYs8tZB0Jbi/7JDt4Ch8hiels8nCC/fIFE9jTkGHW4VvG+RedC0L45r+sHL6+AisllVgZx2XDlOO/7NKplyXPgX5bNw350jCAZin4yzeABvbklyL2WahznKZwi8HypBwuJ0MSoeb7is4QcYwlNIZwdj/bmGboIT7aWka/2HMvliv5EPzQzQH45114rke4+n3ICpjwnr5Tgud8xJ2R3UcriuGQyseww2ScHtoi6+xffrNwYfcA8fLFP+fdBuYIplw/NjNbSfxR28K1xs7jDJh4y+jUQ9TtAqtOrWmpqZmZPwGYWmWpXHNdQ0AAAAASUVORK5CYII=>

[image31]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEcAAAAYCAYAAACoaOA9AAADOUlEQVR4Xu2XS6hNYRTHP0lhoOSZ9/sVQoSQS55JXjfyviJ5JQaSYoRiIiHFUMlAimQm3RHFQIQZE2NloCTP9Tt7rXvWWffsfc4dkfa/frX32v+zz7fX/tb3rZ1SqVKlSv19TYsBp+7CPGF4vOBkHhgarnVVM4RJSpHwTYjBoGbvVSMe4oLyUnhVe7lDJOSpcEo4LdxThjjPGOGFcFI5o54BztOM+glPhPPCMeWBMD14oD1VfXimOA/qn6qeEwq+RsmsaIWwRLkjvK693KGHKbux6Zxy18UeCcfdOWJQ3LcruixcD7HdwnN3fkW56mIHUvYCvW4Kl0IM37MQa6gbqXNymBnwQ1jm4q3KV6F3ykrol9DiPGhbyjy9QjxPPYVPwr4QnyX8FsYLPYTPivfNUc9ohXF9EXY6D1qQMl/R8tBJ9ZKzVOFmM13cZhtxSpMZyHFcs5ZrnJpvRgwYP4n3GqnxrcI4PYZ1zjNWY5sU1hfO1zgPmqjxDSFeqDI5BaqXnM1KfPCFCvFVwnY9nuw8qEXjviSLZKXhHxpR2sQPC/P1OD74CI3tVxbp+UrnQWwcxPeGeKHqJWeHUpQcBtimx3nJiQPMkz14XnKOpupD5yXnoGIzPv63JYcENi2S8ybEKBcrGV8aixXilBWD5Hiq8yBmDPHZIZ4nK4WNIW7lRlmxXVty1jqPPfQWha2f89XOg9jGicfSLVS95PCH9qe8CZPtVj9T1kvYgHmrXgySnY6epBmxw7C77QlxXoy9iD7CN6XNeXgBeFgboa/wXdjlPIh74Gt2HayI5LyLQRXNIf2ByRq9dhcjsd6DaBgfhxhJPZuybrqe7gsXQ4zffBS66Tl9F9BHmSj/D+4c0Xt5D2Jrfx9iDVUmJ4gt75rCjZnSt1JtN4yoXx6enYk6p1sFFkET09o8sF49w5wH3U7F05qG8m3KEtKi0PnOrVoqaxCYj5LHQ7PoxZKAh+e09ZNPnLz/rhG7AP0BjFK4IR1mFIOhI4XBShSJMA9b5aDayxXx9vnMiOuTF99jzIQjin8JXgNTtqYwY/M6XrvXISW+rH9OlKSVSCknSoBvrlJ1xBZbzpoclckp9Z/qDwtD3H0leDvkAAAAAElFTkSuQmCC>

[image32]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADsAAAAXCAYAAAC1Szf+AAACnklEQVR4Xu2XS6iNURTHl1ceySvkOWEiISlFIgMDE1JMPcoEE69kgi6S5JGIAQbXwIAMPPNIGXiVCYWBmTIgZKoY8P+113b3Xb5zz3fvHeh2z69+nbPX3uecb+9v77W+Y9aixf9ihXtETg99JevlqBisywA5LQYbMMFdJoeEvkZw4fH7p8iZRXubPO1OlO9ku5zl/VPdkx7vMf1qsqMt/UgzdstHLlvpitzRaUQ1bMvf8qv7SX6Wi4oxz+VCF/jezXKrPO5tfG292MIw1ppPdr78Jke4wOt363zRVTDZ25YWJy8QdzYzTP6ydBfznVwnV/8dYbbfXVnEesQ4eSYGA2flyxi0FGv22cNycQwGPlpatLxwF+Qkfz9PnnN7TZ3JPpb3YtBS7EkMBg5Zmmzeppvk0HKAOCiPumzTBx4nL9yUI93aDLL0Q5yFUrbVw4o4sqrwVt7y9yXE6OuKNnnX0hbEjfKppaORIUlud89bx3Zm8kvzIEtzWGI1kyMDyaSlXMC1ijhOTh+z99Z4svR1xRw5PsTYpvdDLMK1HvP3M9yrlpIWZ78p/WqyVdQ5sy/knRi0FKOvK6ibA0PsgPxpjcsImf6GpUwNp9wt3r5kqe52mzqTbbfqSRFrj8ECMiplpS3ESUjU3rIElVAKFxRt8gKu8XY++92mzmRXyS9ysAvcLWL0AXfhopvrIWNeydnezrAdiVfBZ6mpJW/ctd7miJV1+B/IZDvlnmCbfFYRx/KB4bKlTIlkUl7ZWhnu4g+XupzhyeuEpayKe+UHObcYA2xpvG4dC5rhTmM+w+wMHoa6hJROwqhr+YWUh+XuLkv/UCJjXMaWkFxyadlg1RfKkxbmslMy3KXmsnP2de7ue7BAcZGqiMmuRYsWLfoOfwDxko3uOzfTJwAAAABJRU5ErkJggg==>

[image33]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADsAAAAXCAYAAAC1Szf+AAACjklEQVR4Xu2XS6hNURjHP0SSFBkgJEoyECaUPDJhxERJiUtKykAMJKkjlEeexUjyTGTgkYlIRMSAlJIiJSVlYGTg+f+1vnX2Ouue67zKpbt/9au9v7XP3uvxrccxKynpLYa7e+Ri2a+2uMo4uTQP/k2GWqhgrHA9RrtzZP+sbKR85o6Su/16hRwgB7lL5CsLDe41+kRjSTXS7qJcKx+5VCqFZ264XfKSXJeUr5JnXRgor8plcqfc4fK7Ln+mIVPl4DzYAVvkJwu9DtPdLxZGCxbKdxYagEAZz1AfOCGPuxE6MDLePZ/EGjJDnpYVN1aoXUi1J8n9EPeXXOOxC/Jm9YmCt3KbX2+1UC8EOoxsiDCiSIq3TByBk/KInFhb3DTv5f08KH7KY35Nh5xLyiJPLaQqTJIvXOb8fgtzGzbJ5W7HTJCH5Rk5s7aoIXfk8+R+jMvIXvbYR3mq+kTBA3kvuZ/l0klxPk+27r+dZuEbHUFKsxiQdrigprQ+c+VXCyMDpCP+sGI0P1v3CgONfZgHE1j8rlnt6k5qs1Axn8nMtulTjQUavM+9ZWGxacR8ecXC3F/kksa7vPy1hSmS89hCY3qCRvEuoDPxpd/T0AN+3TJj5SELIxAXr2ZJV/S4RdDYuMBct7C/5ryRB/Ogw/fjAgcb3NtJLN2amiKuyEetSMVW2Ci/yxF+v93lYBFZbeHUk0LGfJOzsziwFzPiw5LYevduEmNwGjLPitNKxTrbazkU0BBGsWLFkS99Z5x7e106mDWBNK0H85I6pvAd/GChozgusiX9kZUWHqLX0p7rBCrBOzkbczqrd0IjRjlutrCw5UxxORf3BFsS60PbB4x/jZ7+2kXyPxElJSUl/w+/AdFSiRKnxVaRAAAAAElFTkSuQmCC>