"""
Lightweight client for the Deepomatic Studio API.

Fetches the project map (views, edges, concepts) needed to generate
an annotation guide.
"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STUDIO_BASE_URL = "https://studio.deepomatic.com/api"


class StudioClient:
    """Thin wrapper around Studio REST endpoints."""

    def __init__(self, org_slug: str, project_slug: str, token: str | None = None, api_key: str | None = None):
        self.org_slug = org_slug
        self.project_slug = project_slug
        self.base_url = f"{STUDIO_BASE_URL}/orgs/{org_slug}"
        self.dataset_url = f"{self.base_url}/datasets/{project_slug}"

        # Auth – prefer token, fall back to api_key, then env vars
        token = token or os.getenv("DEEPOMATIC_TOKEN")
        api_key = api_key or os.getenv("DEEPOMATIC_API_KEY")

        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif api_key:
            headers["X-API-KEY"] = api_key
        else:
            raise ValueError(
                "No authentication provided. Set DEEPOMATIC_TOKEN or DEEPOMATIC_API_KEY "
                "environment variable, or pass token/api_key explicitly."
            )

        self._client = httpx.Client(headers=headers, timeout=30)

    # ------------------------------------------------------------------
    # Low-level
    # ------------------------------------------------------------------

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    def get_project(self) -> dict:
        """GET /api/orgs/{org}/projects/{project}/"""
        return self._get(f"{self.base_url}/projects/{self.project_slug}/")

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------

    def get_views(self) -> list[dict]:
        """GET /api/orgs/{org}/datasets/{project}/views/ — returns root views."""
        data = self._get(f"{self.dataset_url}/views/")
        return data.get("results", data) if isinstance(data, dict) else data

    def get_view_children(self, view_uuid: str) -> list[dict]:
        """GET /api/orgs/{org}/datasets/{project}/views/{uuid}/children/"""
        data = self._get(f"{self.dataset_url}/views/{view_uuid}/children/")
        return data.get("results", data) if isinstance(data, dict) else data

    def get_views_map(self) -> dict:
        """GET /api/orgs/{org}/datasets/{project}/views/map/
        Returns the full project map with nodes, edges, and concepts.
        """
        return self._get(f"{self.dataset_url}/views/map/")

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def fetch_project_map(self) -> dict:
        """
        Fetch the project map and enrich it with per-view tags (concepts).
        The /views/map/ endpoint gives the tree structure but not which concepts
        belong to each view. We fetch that separately by walking the views.
        """
        # Get the tree structure from /views/map/
        try:
            project_map = self.get_views_map()
            if "nodes" in project_map:
                logger.info("Fetched project map from /views/map/ endpoint.")
        except httpx.HTTPStatusError as exc:
            logger.warning("Could not use /views/map/ (%s). Building map manually.", exc.response.status_code)
            project_map = self._build_map_manually()

        # Build concept id→name lookup
        concept_map = {c["id"]: c["concept_name"] for c in project_map.get("concepts", [])}

        # Enrich nodes with their actual tag (concept) lists by walking the views API
        view_tags = self._fetch_all_view_tags()
        for node in project_map["nodes"]:
            node_id = node["id"]
            tag_ids = view_tags.get(node_id, [])
            # Resolve tag IDs to names
            node["data"]["tag_ids"] = tag_ids
            node["data"]["tag_names"] = [concept_map.get(tid, str(tid)) for tid in tag_ids]

        return project_map

    def _fetch_all_view_tags(self) -> dict[str, list[int]]:
        """Walk root views + children to collect {view_uuid: [tag_id, ...]}."""
        view_tags: dict[str, list[int]] = {}
        root_views = self.get_views()
        queue = list(root_views)

        while queue:
            view = queue.pop(0)
            uuid = view["uuid"]
            tags = view.get("tags", [])
            # tags can be list of ints or list of dicts
            if tags and isinstance(tags[0], dict):
                view_tags[uuid] = [t["id"] for t in tags]
            else:
                view_tags[uuid] = list(tags)

            children = view.get("children", [])
            if isinstance(children, list) and children:
                if isinstance(children[0], str):
                    try:
                        child_views = self.get_view_children(uuid)
                        queue.extend(child_views)
                    except httpx.HTTPStatusError:
                        logger.warning("Could not fetch children for view %s", uuid)
                else:
                    queue.extend(children)

        return view_tags

    def _build_map_manually(self) -> dict:
        """Walk the view tree via /views/ and /children/ to build the map structure."""
        nodes: list[dict] = []
        edges: list[dict] = []
        all_concepts: dict[int, str] = {}

        root_views = self.get_views()
        queue = [(v, None) for v in root_views]

        while queue:
            view, parent_id = queue.pop(0)
            node_id = view["uuid"]
            node = {
                "id": node_id,
                "label": view.get("real_name") or view.get("name", node_id),
                "data": {
                    "parent": parent_id or "",
                    "kind": view.get("kind", ""),
                    "conditions": view.get("conditions", []),
                },
            }
            nodes.append(node)

            if parent_id:
                edges.append({"source": parent_id, "target": node_id, "data": {}})

            # Collect concepts from tags
            for tag in view.get("tags", []):
                tag_id = tag.get("id")
                tag_name = tag.get("name", "")
                if tag_id is not None:
                    all_concepts[tag_id] = tag_name

            # Recurse into children
            children = view.get("children", [])
            if isinstance(children, list) and children:
                # children might be UUIDs or full objects
                if isinstance(children[0], str):
                    # Need to fetch children explicitly
                    try:
                        child_views = self.get_view_children(node_id)
                        for cv in child_views:
                            queue.append((cv, node_id))
                    except httpx.HTTPStatusError:
                        logger.warning("Could not fetch children for view %s", node_id)
                else:
                    for cv in children:
                        queue.append((cv, node_id))

        concepts = [{"id": cid, "concept_name": cname} for cid, cname in all_concepts.items()]

        project_map = {"nodes": nodes, "edges": edges, "concepts": concepts}
        logger.info("Built project map manually: %d nodes, %d edges, %d concepts", len(nodes), len(edges), len(concepts))
        return project_map
