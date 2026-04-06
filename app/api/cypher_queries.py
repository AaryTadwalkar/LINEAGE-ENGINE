UPSTREAM_QUERY = """
MATCH (start:Dataset {uri: $uri})
CALL apoc.path.subgraphAll(start, {
    relationshipFilter: 'CONSUMES>|<PRODUCES',
    maxLevel: $depth
})
YIELD nodes, relationships
RETURN nodes, relationships
"""

# Fallback if APOC is not available — pure Cypher variable-length path
UPSTREAM_QUERY_NO_APOC = """
MATCH path = (start:Dataset {uri: $uri})
              -[:CONSUMES*0..{depth}]->(j:Job)
              -[:CONSUMES*0..{depth}]->(upstream:Dataset)
WHERE start <> upstream
RETURN DISTINCT
    nodes(path) AS path_nodes,
    relationships(path) AS path_rels
LIMIT 1000
"""

DOWNSTREAM_QUERY = """
MATCH path = (start:Dataset {uri: $uri})
              <-[:PRODUCES*0..{depth}]-(j:Job)
              -[:PRODUCES*0..{depth}]->(downstream:Dataset)
WHERE start <> downstream
RETURN DISTINCT
    nodes(path) AS path_nodes,
    relationships(path) AS path_rels
LIMIT 1000
"""

DATASET_EXISTS_QUERY = """
MATCH (d:Dataset {uri: $uri})
RETURN d.uri AS uri LIMIT 1
"""
