"""FalkorDB database client layer with query execution and health checks."""

import logging
from typing import Any, Optional
from falkordb import FalkorDB
from app.config import config

logger = logging.getLogger(__name__)


class FalkorDBClient:
    """Manages connection and query execution against FalkorDB."""

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None, graph_name: Optional[str] = None):
        self.host = host or config.host
        self.port = port or config.port
        self.graph_name = graph_name or config.graph_name
        self._driver: Optional[FalkorDB] = None
        self._graph = None

    def connect(self):
        """Establishes connection to FalkorDB driver and selects the target graph."""
        try:
            self._driver = FalkorDB(host=self.host, port=self.port)
            self._graph = self._driver.select_graph(self.graph_name)
            return self._graph
        except Exception as e:
            logger.error(f"Failed to connect to FalkorDB at {self.host}:{self.port} - {e}")
            raise ConnectionError(
                f"Could not connect to FalkorDB container at {self.host}:{self.port}. "
                f"Ensure Docker container is running (e.g., docker ps)."
            ) from e

    @property
    def graph(self):
        if self._graph is None:
            self.connect()
        return self._graph

    def is_healthy(self) -> bool:
        """Checks if FalkorDB is reachable and responsive."""
        try:
            res = self.query("RETURN 1 as ping")
            return len(res) > 0 and res[0][0] == 1
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def query(self, cypher: str, params: Optional[dict[str, Any]] = None) -> list:
        """Executes a Cypher query with optional parameterized inputs.
        
        Returns the raw result_set rows.
        """
        try:
            res = self.graph.query(cypher, params or {})
            return res.result_set
        except Exception as e:
            logger.error(f"Cypher query error: {e} | Query: {cypher} | Params: {params}")
            raise RuntimeError(f"FalkorDB Cypher execution failed: {e}") from e

    def query_with_header(self, cypher: str, params: Optional[dict[str, Any]] = None) -> tuple[list[str], list]:
        """Executes a Cypher query and returns (header_column_names, rows)."""
        try:
            res = self.graph.graph_query(cypher, params or {})
            headers = [col[1].decode("utf-8") if isinstance(col[1], bytes) else str(col[1]) for col in res.header] if hasattr(res, "header") and res.header else []
            return headers, res.result_set
        except Exception:
            # Fallback for standard query object
            res = self.graph.query(cypher, params or {})
            headers = getattr(res, "header", [])
            header_names = []
            if headers:
                for h in headers:
                    name = h[1].decode("utf-8") if isinstance(h[1], bytes) else str(h[1])
                    header_names.append(name)
            return header_names, res.result_set

    def delete_graph(self):
        """Removes the entire graph (used for reset/testing)."""
        try:
            self.graph.delete()
            self._graph = None
        except Exception as e:
            logger.warning(f"Could not delete graph {self.graph_name}: {e}")


# Singleton client instance
db_client = FalkorDBClient()
