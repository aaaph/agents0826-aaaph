// Neo4j schema v2 for agent memory — adds project scoping + vector search.
// Apply via migrate_v2.py (also backfills project + embeddings).
//
// Requires Neo4j 5.13+ (vector indexes). Verified on 5.26.24 Community.
// NOTE: all memory objects are namespaced to the :Memory label and the
// memory_* index prefix, so this schema can safely share a Neo4j instance
// with other graphs (e.g. an existing GraphRAG) without colliding.

// --- carried over from v1 (idempotent) ---
CREATE CONSTRAINT memory_path_unique IF NOT EXISTS
FOR (m:Memory) REQUIRE m.path IS UNIQUE;

CREATE FULLTEXT INDEX memory_fulltext IF NOT EXISTS
FOR (m:Memory) ON EACH [m.content, m.path];

// --- v2: project scoping ---
// Every Memory gets a `project` tag. Shared knowledge uses 'global'.
// Per-project queries match (project = $project OR project = 'global').
CREATE INDEX memory_project IF NOT EXISTS
FOR (m:Memory) ON (m.project);

// --- v2: vector index for semantic (multilingual) search ---
// 384 dims = intfloat/multilingual-e5-small. Cosine similarity (vectors are
// L2-normalized at write time, so cosine == dot product).
CREATE VECTOR INDEX memory_embedding IF NOT EXISTS
FOR (m:Memory) ON (m.embedding)
OPTIONS { indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
} };
