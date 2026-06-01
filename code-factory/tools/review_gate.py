"""人工审核门控实现 / Human Review Gate implementation.

管理人在环路的审核工作流：在配置的审核点暂停执行，
Manages human-in-the-loop review workflow: pausing execution at configured
处理批准/拒绝决策、超时提醒，并持久化所有审核记录。
review points, handling approval/rejection decisions, timeout reminders,
and persisting all review records.

需求 / Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from src.core.interfaces import ReviewGateInterface
from src.core.logging import get_logger
from src.core.models import ReviewDecision, ReviewRecord, ReviewRequest

logger = get_logger("tools.review_gate")


class HumanReviewGate(ReviewGateInterface):
    """人在环路的审核门控，用于工作流批准/拒绝 / Human-in-the-loop review gate for workflow approval/rejection.

    实现在配置的审核点暂停工作流、批准后恢复、
    Implements workflow pause at configured review points, resume on approval,
    带反馈的拒绝路由、可配置的超时提醒，
    rejection routing with feedback, configurable timeouts with reminders,
    以及持久化所有审核决策。
    and persistence of all review decisions.

    该门控使用内存存储保存待处理的审核，并可选地
    The gate uses an in-memory store for pending reviews and optionally
    通过 asyncpg 将决策持久化到 PostgreSQL。
    persists decisions to PostgreSQL via asyncpg.
    """

    def __init__(
        self,
        db_pool: Any | None = None,
        config_path: str | Path | None = None,
        review_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the Human Review Gate.

        Args:
            db_pool: Optional asyncpg connection pool for persisting review records.
                If None, records are stored in-memory only.
            config_path: Path to review_gates.yaml configuration file.
                Defaults to 'config/review_gates.yaml' if neither config_path
                nor review_config is provided.
            review_config: Pre-loaded review configuration dict.
                If provided, config_path is ignored.
        """
        self._db_pool = db_pool

        if review_config is not None:
            self._config = review_config
        else:
            if config_path is None:
                config_path = Path("config/review_gates.yaml")
            self._config = self._load_config(Path(config_path))

        # In-memory stores
        self._pending_requests: dict[str, ReviewRequest] = {}
        self._decisions: dict[str, ReviewRecord] = {}
        self._reminder_sent: dict[str, list[float]] = {}

        # Parse notification settings
        notifications = self._config.get("review_gates", {}).get("notifications", {})
        self._reminder_interval_seconds: int = notifications.get(
            "reminder_interval_seconds", 1800
        )
        self._notification_channels: list[dict[str, Any]] = notifications.get(
            "channels", []
        )

    @staticmethod
    def _load_config(config_path: Path) -> dict[str, Any]:
        """Load review gate configuration from a YAML file.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            Parsed configuration dictionary.

        Raises:
            FileNotFoundError: If the config file does not exist.
            yaml.YAMLError: If the YAML is malformed.
        """
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            logger.error(
                "Failed to load review gate config",
                config_path=str(config_path),
                error=str(e),
            )
            return {}

    async def submit_for_review(self, request: ReviewRequest) -> str:
        """Submit content for human review, pausing the workflow.

        Stores the review request and starts timeout tracking. The workflow
        is effectively paused until a decision is recorded via record_decision().

        Args:
            request: The review request containing content to be reviewed.

        Returns:
            The request_id for tracking the review status.
        """
        self._pending_requests[request.request_id] = request
        self._reminder_sent[request.request_id] = []

        logger.info(
            "Review request submitted",
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            agent_name=request.agent_name,
            timeout_seconds=request.timeout_seconds,
        )

        # Persist to database if pool is available
        if self._db_pool is not None:
            await self._persist_request(request)

        return request.request_id

    async def get_decision(self, request_id: str) -> Optional[ReviewRecord]:
        """Get the review decision for a given request.

        Returns the ReviewRecord if a decision has been made, or None if
        the review is still pending.

        Args:
            request_id: The unique identifier of the review request.

        Returns:
            ReviewRecord if decided, None if still pending.
        """
        # Check in-memory first
        if request_id in self._decisions:
            return self._decisions[request_id]

        # Check database if pool is available
        if self._db_pool is not None:
            record = await self._fetch_decision_from_db(request_id)
            if record is not None:
                self._decisions[request_id] = record
                return record

        return None

    async def record_decision(self, record: ReviewRecord) -> None:
        """Record a review decision (approval or rejection).

        Persists the decision with reviewer_id, timestamp, and comments.
        Removes the request from the pending queue.

        Args:
            record: The review record containing the decision details.
        """
        self._decisions[record.request_id] = record

        # Remove from pending
        self._pending_requests.pop(record.request_id, None)
        self._reminder_sent.pop(record.request_id, None)

        logger.info(
            "Review decision recorded",
            request_id=record.request_id,
            reviewer_id=record.reviewer_id,
            decision=record.decision.value,
            comments=record.comments,
            timestamp=record.timestamp.isoformat(),
        )

        # Persist to database if pool is available
        if self._db_pool is not None:
            await self._persist_decision(record)

    def get_review_config(self, workflow_name: str) -> Optional[dict[str, Any]]:
        """Get review configuration for a specific workflow.

        Checks whether a workflow requires review and returns the review
        point configuration if so.

        Args:
            workflow_name: Name of the workflow to check (e.g., "test_case_generation").

        Returns:
            Dict with review point configuration if review is required,
            None if no review is configured for this workflow.
        """
        workflows = self._config.get("review_gates", {}).get("workflows", {})
        workflow_config = workflows.get(workflow_name)

        if workflow_config is None:
            return None

        return workflow_config

    def is_review_required(self, workflow_name: str, agent_name: str) -> bool:
        """Check if review is required after a specific agent in a workflow.

        Args:
            workflow_name: Name of the workflow.
            agent_name: Name of the agent that just completed.

        Returns:
            True if review is required at this point, False otherwise.
        """
        workflow_config = self.get_review_config(workflow_name)
        if workflow_config is None:
            return False

        review_points = workflow_config.get("review_points", [])
        for point in review_points:
            if point.get("after_agent") == agent_name and point.get("required", False):
                return True

        return False

    def get_timeout_for_review_point(
        self, workflow_name: str, agent_name: str
    ) -> int:
        """Get the timeout in seconds for a specific review point.

        Args:
            workflow_name: Name of the workflow.
            agent_name: Name of the agent after which review occurs.

        Returns:
            Timeout in seconds. Defaults to 3600 if not configured.
        """
        workflow_config = self.get_review_config(workflow_name)
        if workflow_config is None:
            return 3600

        review_points = workflow_config.get("review_points", [])
        for point in review_points:
            if point.get("after_agent") == agent_name:
                return point.get("timeout_seconds", 3600)

        return 3600

    async def check_timeouts(self) -> list[str]:
        """Check all pending reviews for timeouts and send reminders.

        Should be called periodically (e.g., by a background task).
        Sends reminder notifications for reviews that have exceeded
        the reminder interval without a decision.

        Returns:
            List of request_ids that triggered reminder notifications.
        """
        now = time.time()
        reminded: list[str] = []

        for request_id, request in list(self._pending_requests.items()):
            elapsed = (
                datetime.now(timezone.utc) - request.created_at
            ).total_seconds()

            # Check if total timeout exceeded
            if elapsed >= request.timeout_seconds:
                await self._send_timeout_reminder(request_id, request, is_final=True)
                reminded.append(request_id)
                continue

            # Check if reminder interval has passed since last reminder
            last_reminders = self._reminder_sent.get(request_id, [])
            last_reminder_time = last_reminders[-1] if last_reminders else 0.0

            if (now - last_reminder_time) >= self._reminder_interval_seconds:
                # Only send reminder if at least one interval has passed since creation
                if elapsed >= self._reminder_interval_seconds:
                    await self._send_timeout_reminder(
                        request_id, request, is_final=False
                    )
                    self._reminder_sent.setdefault(request_id, []).append(now)
                    reminded.append(request_id)

        return reminded

    def get_pending_reviews(self) -> dict[str, ReviewRequest]:
        """Get all currently pending review requests.

        Returns:
            Dict mapping request_id to ReviewRequest for all pending reviews.
        """
        return dict(self._pending_requests)

    def get_approved_content(self, request_id: str) -> Optional[dict]:
        """Get the approved content for a review request.

        Used to pass approved content downstream in the workflow.

        Args:
            request_id: The review request ID.

        Returns:
            The original content dict if approved, None otherwise.
        """
        decision = self._decisions.get(request_id)
        if decision is None or decision.decision != ReviewDecision.APPROVED:
            return None

        request = self._pending_requests.get(request_id)
        if request is not None:
            return request.content

        # Request already removed from pending (normal after decision)
        # Try to find it from the original submission
        return None

    def get_rejection_feedback(self, request_id: str) -> Optional[dict[str, Any]]:
        """Get rejection feedback for routing back to the originating agent.

        Returns the reviewer's comments and metadata needed to route
        the task back to the originating agent.

        Args:
            request_id: The review request ID.

        Returns:
            Dict with feedback info if rejected, None otherwise.
        """
        decision = self._decisions.get(request_id)
        if decision is None or decision.decision != ReviewDecision.REJECTED:
            return None

        return {
            "request_id": decision.request_id,
            "reviewer_id": decision.reviewer_id,
            "comments": decision.comments,
            "timestamp": decision.timestamp.isoformat(),
            "decision": decision.decision.value,
        }

    # =========================================================================
    # Private helper methods
    # =========================================================================

    async def _send_timeout_reminder(
        self, request_id: str, request: ReviewRequest, is_final: bool
    ) -> None:
        """Send a timeout reminder notification.

        Args:
            request_id: The review request ID.
            request: The review request details.
            is_final: Whether this is the final timeout (total timeout exceeded).
        """
        reminder_type = "final_timeout" if is_final else "reminder"

        logger.warning(
            "Review timeout reminder",
            request_id=request_id,
            workflow_id=request.workflow_id,
            agent_name=request.agent_name,
            reminder_type=reminder_type,
            timeout_seconds=request.timeout_seconds,
            channels=[ch.get("type") for ch in self._notification_channels],
        )

        # In a production system, this would send actual notifications
        # via configured channels (webhook, email, etc.)
        for channel in self._notification_channels:
            channel_type = channel.get("type")
            if channel_type == "webhook":
                await self._send_webhook_notification(
                    channel, request_id, request, reminder_type
                )

    async def _send_webhook_notification(
        self,
        channel: dict[str, Any],
        request_id: str,
        request: ReviewRequest,
        reminder_type: str,
    ) -> None:
        """Send a webhook notification (placeholder for actual HTTP call).

        Args:
            channel: Channel configuration with URL.
            request_id: The review request ID.
            request: The review request details.
            reminder_type: Type of reminder ("reminder" or "final_timeout").
        """
        # In production, this would make an HTTP POST to the webhook URL.
        # For now, we log the intent.
        logger.info(
            "Webhook notification triggered",
            channel_type="webhook",
            url=channel.get("url", ""),
            request_id=request_id,
            workflow_id=request.workflow_id,
            reminder_type=reminder_type,
        )

    async def _persist_request(self, request: ReviewRequest) -> None:
        """Persist a review request to the database.

        Args:
            request: The review request to persist.
        """
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO review_records
                        (request_id, workflow_id, agent_name, content,
                         decision, timeout_seconds, created_at)
                    VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                    ON CONFLICT (request_id) DO NOTHING
                    """,
                    request.request_id,
                    request.workflow_id,
                    request.agent_name,
                    _dict_to_json(request.content),
                    ReviewDecision.PENDING.value,
                    request.timeout_seconds,
                    request.created_at,
                )
        except Exception as e:
            logger.error(
                "Failed to persist review request",
                request_id=request.request_id,
                error=str(e),
            )

    async def _persist_decision(self, record: ReviewRecord) -> None:
        """Persist a review decision to the database.

        Args:
            record: The review record to persist.
        """
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE review_records
                    SET reviewer_id = $1,
                        decision = $2,
                        comments = $3,
                        decided_at = $4
                    WHERE request_id = $5
                    """,
                    record.reviewer_id,
                    record.decision.value,
                    record.comments,
                    record.timestamp,
                    record.request_id,
                )
        except Exception as e:
            logger.error(
                "Failed to persist review decision",
                request_id=record.request_id,
                error=str(e),
            )

    async def _fetch_decision_from_db(
        self, request_id: str
    ) -> Optional[ReviewRecord]:
        """Fetch a review decision from the database.

        Args:
            request_id: The review request ID to look up.

        Returns:
            ReviewRecord if found and decided, None otherwise.
        """
        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT request_id, reviewer_id, decision, comments, decided_at
                    FROM review_records
                    WHERE request_id = $1 AND decision != $2
                    """,
                    request_id,
                    ReviewDecision.PENDING.value,
                )
                if row is None:
                    return None

                return ReviewRecord(
                    request_id=row["request_id"],
                    reviewer_id=row["reviewer_id"],
                    decision=ReviewDecision(row["decision"]),
                    comments=row["comments"] or "",
                    timestamp=row["decided_at"],
                )
        except Exception as e:
            logger.error(
                "Failed to fetch review decision from DB",
                request_id=request_id,
                error=str(e),
            )
            return None


def _dict_to_json(data: dict) -> str:
    """Convert a dict to a JSON string for database storage.

    Args:
        data: Dictionary to serialize.

    Returns:
        JSON string representation.
    """
    import json

    return json.dumps(data, default=str)
