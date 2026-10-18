// TraceGuard AI - Neo4j schema constraints and indexes.
// Applied by the backend graph bootstrap on first connection (M6).
// Every entity is scoped by case_id; (case_id, value) is unique per label.

CREATE CONSTRAINT username_key IF NOT EXISTS
  FOR (n:Username) REQUIRE (n.case_id, n.value) IS UNIQUE;

CREATE CONSTRAINT email_key IF NOT EXISTS
  FOR (n:Email) REQUIRE (n.case_id, n.value) IS UNIQUE;

CREATE CONSTRAINT domain_key IF NOT EXISTS
  FOR (n:Domain) REQUIRE (n.case_id, n.value) IS UNIQUE;

CREATE CONSTRAINT ip_key IF NOT EXISTS
  FOR (n:IpAddress) REQUIRE (n.case_id, n.value) IS UNIQUE;

CREATE CONSTRAINT file_key IF NOT EXISTS
  FOR (n:File) REQUIRE (n.case_id, n.sha256) IS UNIQUE;

CREATE CONSTRAINT wallet_key IF NOT EXISTS
  FOR (n:Wallet) REQUIRE (n.case_id, n.value) IS UNIQUE;

CREATE CONSTRAINT tx_key IF NOT EXISTS
  FOR (n:Transaction) REQUIRE (n.case_id, n.value) IS UNIQUE;

CREATE CONSTRAINT evidence_key IF NOT EXISTS
  FOR (n:Evidence) REQUIRE (n.case_id, n.evidence_id) IS UNIQUE;

CREATE CONSTRAINT finding_key IF NOT EXISTS
  FOR (n:Finding) REQUIRE (n.case_id, n.finding_id) IS UNIQUE;

CREATE INDEX case_scope IF NOT EXISTS FOR (n:Evidence) ON (n.case_id);
