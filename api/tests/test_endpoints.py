from __future__ import annotations


class TestGetLesson:
    """GET /tenants/{tenant_id}/users/{user_id}/lessons/{lesson_id}"""

    URL = "/tenants/1/users/10/lessons/100"

    async def test_returns_assembled_lesson(self, client):
        resp = await client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()

        lesson = data["lesson"]
        assert lesson["id"] == 100
        assert lesson["slug"] == "ai-basics"
        assert lesson["title"] == "AI Basics"

        blocks = data["blocks"]
        assert len(blocks) == 3
        assert [b["position"] for b in blocks] == [1, 2, 3]
        assert [b["id"] for b in blocks] == [200, 201, 202]

    async def test_variant_selection_tenant_override(self, client):
        resp = await client.get(self.URL)
        blocks = resp.json()["blocks"]
        # Block 200 has an Acme-specific override (tenant_id=1)
        variant = blocks[0]["variant"]
        assert variant["id"] == 1100
        assert variant["tenant_id"] == 1

    async def test_variant_selection_default_fallback(self, client):
        resp = await client.get(self.URL)
        blocks = resp.json()["blocks"]
        # Block 201 has no tenant-specific variant → default (tenant_id=null)
        variant = blocks[1]["variant"]
        assert variant["id"] == 1001
        assert variant["tenant_id"] is None

    async def test_progress_per_block(self, client):
        resp = await client.get(self.URL)
        blocks = resp.json()["blocks"]
        assert blocks[0]["user_progress"] == "completed"  # block 200
        assert blocks[1]["user_progress"] == "seen"  # block 201
        assert blocks[2]["user_progress"] is None  # block 202

    async def test_progress_summary(self, client):
        resp = await client.get(self.URL)
        summary = resp.json()["progress_summary"]
        assert summary["total_blocks"] == 3
        assert summary["seen_blocks"] == 2
        assert summary["completed_blocks"] == 1
        assert summary["last_seen_block_id"] == 201
        assert summary["completed"] is False

    async def test_cross_tenant_user_returns_404(self, client):
        # User 20 belongs to tenant 2, not tenant 1
        resp = await client.get("/tenants/1/users/20/lessons/100")
        assert resp.status_code == 404

    async def test_nonexistent_tenant_returns_404(self, client):
        resp = await client.get("/tenants/999/users/10/lessons/100")
        assert resp.status_code == 404

    async def test_nonexistent_lesson_returns_404(self, client):
        resp = await client.get("/tenants/1/users/10/lessons/999")
        assert resp.status_code == 404


class TestPutProgress:
    """PUT /tenants/{tenant_id}/users/{user_id}/lessons/{lesson_id}/progress"""

    URL = "/tenants/1/users/10/lessons/100/progress"

    async def test_mark_seen(self, client):
        resp = await client.put(self.URL, json={"block_id": 202, "status": "seen"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["stored_status"] == "seen"
        # 200=completed, 201=seen, 202=seen → all 3 counted as "seen"
        assert data["progress_summary"]["seen_blocks"] == 3

    async def test_mark_completed(self, client):
        # Bob (user 11) has no prior progress
        resp = await client.put(
            "/tenants/1/users/11/lessons/100/progress",
            json={"block_id": 200, "status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["stored_status"] == "completed"

    async def test_monotonic_no_downgrade(self, client):
        # Block 200 already completed for Alice → stays completed
        resp = await client.put(self.URL, json={"block_id": 200, "status": "seen"})
        assert resp.status_code == 200
        assert resp.json()["stored_status"] == "completed"

    async def test_invalid_block_returns_400(self, client):
        resp = await client.put(self.URL, json={"block_id": 999, "status": "seen"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_block"

    async def test_invalid_status_returns_400(self, client):
        resp = await client.put(
            self.URL, json={"block_id": 200, "status": "invalid"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_status"

    async def test_cross_tenant_returns_404(self, client):
        resp = await client.put(
            "/tenants/1/users/20/lessons/100/progress",
            json={"block_id": 200, "status": "seen"},
        )
        assert resp.status_code == 404

    async def test_progress_summary_updated(self, client):
        # Mark block 202 as seen, then verify updated summary
        resp = await client.put(self.URL, json={"block_id": 202, "status": "seen"})
        assert resp.status_code == 200
        summary = resp.json()["progress_summary"]
        assert summary["seen_blocks"] == 3
        assert summary["last_seen_block_id"] == 202
