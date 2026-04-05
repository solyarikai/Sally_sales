"""Crona API client with automatic JWT token management."""
import os
import time
import httpx
from typing import Any


BASE_URL = "https://api.crona.ai"


class CronaClient:
    def __init__(self, email: str | None = None, password: str | None = None):
        self.email = email or os.environ["CRONA_EMAIL"]
        self.password = password or os.environ["CRONA_PASSWORD"]
        self._token: str | None = None
        self._http = httpx.Client(base_url=BASE_URL, timeout=60)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _login(self) -> None:
        r = self._http.post(
            "/api/clients/sign_in",
            json={"client": {"email": self.email, "password": self.password}},
        )
        r.raise_for_status()
        self._token = r.headers.get("Authorization") or r.json().get("jwt_token")
        if self._token and not self._token.startswith("Bearer "):
            self._token = f"Bearer {self._token}"

    def _headers(self) -> dict:
        if not self._token:
            self._login()
        return {"Authorization": self._token}

    def _get(self, path: str, **params) -> Any:
        r = self._http.get(path, headers=self._headers(), params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: dict | None = None) -> Any:
        r = self._http.post(path, headers=self._headers(), json=json)
        r.raise_for_status()
        return r.json() if r.content else None

    def _put(self, path: str, json: dict | None = None) -> Any:
        r = self._http.put(path, headers=self._headers(), json=json)
        r.raise_for_status()
        return r.json() if r.content else None

    def _delete(self, path: str) -> None:
        r = self._http.delete(path, headers=self._headers())
        r.raise_for_status()

    def _upload(self, path: str, source_type: str, file_path: str) -> Any:
        with open(file_path, "rb") as f:
            r = self._http.post(
                path,
                headers=self._headers(),
                files={"file": (os.path.basename(file_path), f, "text/csv")},
                data={"source_type": source_type},
            )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # WhoAmI
    # ------------------------------------------------------------------

    def whoami(self) -> dict:
        return self._get("/api/whoami")

    def credits_balance(self) -> int:
        return self._get("/api/whoami/credits_balance")["credits_balance"]

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def list_projects(self) -> list:
        return self._get("/api/projects")

    def get_project(self, project_id: int) -> dict:
        return self._get(f"/api/projects/{project_id}")

    def create_project(
        self,
        name: str,
        source_type: str | None = None,
        source_urls: list[str] | None = None,
        sales_nav_cookies: str | None = None,
        sales_nav_user_agent: str | None = None,
        with_preprocessing: bool = True,
        max_pages: int | None = None,
    ) -> dict:
        body: dict = {"name": name}
        if source_type:
            body["source_type"] = source_type
        if source_urls:
            body["source_urls"] = source_urls
        if sales_nav_cookies:
            body["sales_nav_cookies"] = sales_nav_cookies
        if sales_nav_user_agent:
            body["sales_nav_user_agent"] = sales_nav_user_agent
        if source_type == "sales_navigator":
            body["with_preprocessing"] = with_preprocessing
        if max_pages:
            body["max_pages"] = max_pages
        return self._post("/api/projects", json={"project": body})

    def update_project(self, project_id: int, **kwargs) -> dict:
        return self._put(f"/api/projects/{project_id}", json={"project": kwargs})

    def delete_project(self, project_id: int) -> None:
        self._delete(f"/api/projects/{project_id}")

    def upload_source_file(self, project_id: int, source_type: str, file_path: str) -> dict:
        return self._upload(f"/api/projects/{project_id}/source_file", source_type, file_path)

    def get_project_status(self, project_id: int) -> dict:
        return self._get(f"/api/projects/{project_id}/status")

    def get_last_results(self, project_id: int, page: int = 1) -> dict:
        return self._get(f"/api/projects/{project_id}/last_results", page=page)

    def download_last_results_url(self, project_id: int) -> str:
        return f"{BASE_URL}/api/projects/{project_id}/download_last_results"

    # ------------------------------------------------------------------
    # Enrichers
    # ------------------------------------------------------------------

    def list_enricher_types(self) -> list:
        return self._get("/api/enricher_types")

    def list_filter_types(self) -> list:
        return self._get("/api/filter_types")

    def list_enrichers(self, project_id: int) -> list:
        return self._get(f"/api/projects/{project_id}/enrichers")

    def get_enricher(self, project_id: int, enricher_id: int) -> dict:
        return self._get(f"/api/projects/{project_id}/enrichers/{enricher_id}")

    def create_enricher(
        self,
        project_id: int,
        name: str,
        field_name: str,
        enricher_type: str,
        order: int,
        code: str = "",
        arguments: dict | None = None,
    ) -> dict:
        return self._post(
            f"/api/projects/{project_id}/enrichers",
            json={
                "enricher": {
                    "name": name,
                    "field_name": field_name,
                    "type": enricher_type,
                    "order": order,
                    "code": code,
                    "arguments": arguments or {},
                }
            },
        )

    def update_enricher(self, project_id: int, enricher_id: int, **kwargs) -> dict:
        return self._put(
            f"/api/projects/{project_id}/enrichers/{enricher_id}",
            json={"enricher": kwargs},
        )

    def delete_enricher(self, project_id: int, enricher_id: int) -> None:
        self._delete(f"/api/projects/{project_id}/enrichers/{enricher_id}")

    def get_available_columns(self, project_id: int, enricher_id: int) -> list:
        return self._get(f"/api/projects/{project_id}/enrichers/{enricher_id}/available_columns")

    # ------------------------------------------------------------------
    # Project Runs
    # ------------------------------------------------------------------

    def run_project(
        self,
        project_id: int,
        enricher_id: int | None = None,
        run_dataset_id: int | None = None,
        required_amount: int | None = None,
    ) -> dict:
        return self._post(
            f"/api/projects/{project_id}/project_runs",
            json={
                "enricher_id": enricher_id,
                "run_dataset_id": run_dataset_id,
                "required_amount": required_amount,
            },
        )

    def get_project_run(self, project_id: int, run_id: int) -> dict:
        return self._get(f"/api/projects/{project_id}/project_runs/{run_id}")

    def cancel_project_run(self, project_id: int, run_id: int) -> dict:
        return self._put(f"/api/projects/{project_id}/project_runs/{run_id}/cancel")

    def wait_for_completion(self, project_id: int, poll_interval: int = 10, timeout: int = 3600) -> dict:
        """Poll project status until completed/failed/cancelled."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_project_status(project_id)
            if status["status"] in ("completed", "failed", "cancelled"):
                return status
            time.sleep(poll_interval)
        raise TimeoutError(f"Project {project_id} did not finish within {timeout}s")

    # ------------------------------------------------------------------
    # Enricher Runs
    # ------------------------------------------------------------------

    def list_enricher_runs(self, project_id: int, enricher_id: int) -> list:
        return self._get(f"/api/projects/{project_id}/enrichers/{enricher_id}/enricher_runs")

    def get_enricher_run_data(self, project_id: int, enricher_id: int, run_id: int, page: int = 1) -> dict:
        return self._get(
            f"/api/projects/{project_id}/enrichers/{enricher_id}/enricher_runs/{run_id}",
            page=page,
        )

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------

    def get_subscription(self) -> dict:
        return self._get("/api/billing/subscription")

    def list_plans(self) -> list:
        return self._get("/api/billing/plans")

    def spent_credits(self) -> list:
        return self._get("/api/billing/spent_credits")
