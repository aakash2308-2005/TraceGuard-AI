"""Neo4j async driver management."""

from functools import lru_cache

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import get_settings


@lru_cache
def get_graph_driver() -> AsyncDriver:
    """Return a cached async Neo4j driver."""
    settings = get_settings()
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


async def close_graph_driver() -> None:
    """Close the cached driver (called on shutdown)."""
    driver = get_graph_driver()
    await driver.close()
    get_graph_driver.cache_clear()
