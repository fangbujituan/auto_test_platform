"""Unit tests for the Human Review Gate.

Tests cover:
- Submit for review and pause workflow
- Resume on approval
- Rejection with feedback routing
- Timeout notification triggering
- Review record persistence
- Configuration loading and review point detection
"""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import ReviewDecision, ReviewRecord, ReviewRequest
from tools.review_gate import HumanReviewGate


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_config():
    """Sample review gates configuration."""
    return {
        "review_gates": {
            "workflows": {
                "test_case_generation": {
                    "review_points": [
                        {
                            "after_agent": "testcase_agent",
                            "required": True,
                            "timeout_seconds": 3600,
                        }
                    ]
                },
                "test_script_generation": {
                    "review_points": [
                        {
                            "after_agent": "testscript_agent",
                            "required": True,
                            "timeout_seconds": 7200,
                        }
                    ]
                },
            },
            "notifications": {
                "reminder_interval_seconds": 1800,
                "channels": [
                    {"type": "webhook", "url": "https://example.com/webhook"}
                ],
            },
        }
    }


@pytest.fixture
def review_gate(sample_config):
    """Create a HumanReviewGate with in-memory storage."""
    return HumanReviewGate(review_config=sample_config)


@pytest.fixture
def sample_request():
    """Create a sample review request."""
    return ReviewRequest(
        request_id="req-001",
        workflow_id="wf-001",
        agent_name="testcase_agent",
        content={"test_cases": [{"name": "test_login", "steps": ["step1"]}]},
        created_at=datetime.now(timezone.utc),
        timeout_seconds=3600,
    )


@pytest.fixture
def sample_approval():
    """Create a sample approval record."""
    return ReviewRecord(
        request_id="req-001",
        reviewer_id="reviewer-alice",
        decision=ReviewDecision.APPROVED,
        comments="Looks good, approved.",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_rejection():
    """Create a sample rejection record."""
    return ReviewRecord(
        request_id="req-001",
        reviewer_id="reviewer-bob",
        decision=ReviewDecision.REJECTED,
        comments="Missing edge case for empty input.",
        timestamp=datetime.now(timezone.utc),
    )


# =============================================================================
# Test: Submit for Review
# =============================================================================


class TestSubmitForReview:
    """Tests for submit_for_review method."""

    async def test_submit_returns_request_id(self, review_gate, sample_request):
        """submit_for_review should return the request_id."""
        result = await review_gate.submit_for_review(sample_request)
        assert result == "req-001"

    async def test_submit_stores_pending_request(self, review_gate, sample_request):
        """Submitted request should be stored in pending requests."""
        await review_gate.submit_for_review(sample_request)
        pending = review_gate.get_pending_reviews()
        assert "req-001" in pending
        assert pending["req-001"] == sample_request

    async def test_submit_initializes_reminder_tracking(
        self, review_gate, sample_request
    ):
        """Submitted request should initialize reminder tracking."""
        await review_gate.submit_for_review(sample_request)
        assert "req-001" in review_gate._reminder_sent
        assert review_gate._reminder_sent["req-001"] == []

    async def test_get_decision_returns_none_for_pending(
        self, review_gate, sample_request
    ):
        """get_decision should return None for a pending review."""
        await review_gate.submit_for_review(sample_request)
        decision = await review_gate.get_decision("req-001")
        assert decision is None


# =============================================================================
# Test: Record Decision (Approval)
# =============================================================================


class TestApproval:
    """Tests for approval workflow."""

    async def test_record_approval(self, review_gate, sample_request, sample_approval):
        """Recording an approval should store the decision."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_approval)

        decision = await review_gate.get_decision("req-001")
        assert decision is not None
        assert decision.decision == ReviewDecision.APPROVED
        assert decision.reviewer_id == "reviewer-alice"
        assert decision.comments == "Looks good, approved."

    async def test_approval_removes_from_pending(
        self, review_gate, sample_request, sample_approval
    ):
        """Approval should remove the request from pending."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_approval)

        pending = review_gate.get_pending_reviews()
        assert "req-001" not in pending


# =============================================================================
# Test: Record Decision (Rejection)
# =============================================================================


class TestRejection:
    """Tests for rejection workflow."""

    async def test_record_rejection(
        self, review_gate, sample_request, sample_rejection
    ):
        """Recording a rejection should store the decision with feedback."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_rejection)

        decision = await review_gate.get_decision("req-001")
        assert decision is not None
        assert decision.decision == ReviewDecision.REJECTED
        assert decision.reviewer_id == "reviewer-bob"
        assert decision.comments == "Missing edge case for empty input."

    async def test_rejection_feedback_routing(
        self, review_gate, sample_request, sample_rejection
    ):
        """Rejection should provide feedback for routing back to agent."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_rejection)

        feedback = review_gate.get_rejection_feedback("req-001")
        assert feedback is not None
        assert feedback["reviewer_id"] == "reviewer-bob"
        assert feedback["comments"] == "Missing edge case for empty input."
        assert feedback["decision"] == "rejected"
        assert feedback["request_id"] == "req-001"

    async def test_no_feedback_for_approved(
        self, review_gate, sample_request, sample_approval
    ):
        """get_rejection_feedback should return None for approved requests."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_approval)

        feedback = review_gate.get_rejection_feedback("req-001")
        assert feedback is None

    async def test_no_feedback_for_unknown_request(self, review_gate):
        """get_rejection_feedback should return None for unknown requests."""
        feedback = review_gate.get_rejection_feedback("nonexistent")
        assert feedback is None


# =============================================================================
# Test: Timeout and Reminders
# =============================================================================


class TestTimeouts:
    """Tests for timeout handling and reminder notifications."""

    async def test_no_reminder_before_interval(self, review_gate, sample_request):
        """No reminder should be sent before the interval elapses."""
        await review_gate.submit_for_review(sample_request)
        reminded = await review_gate.check_timeouts()
        assert reminded == []

    async def test_reminder_after_interval(self, review_gate, sample_config):
        """Reminder should be sent after the reminder interval elapses."""
        # Create a request that was created long ago
        old_request = ReviewRequest(
            request_id="req-old",
            workflow_id="wf-001",
            agent_name="testcase_agent",
            content={"test": "data"},
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            timeout_seconds=3600,
        )
        await review_gate.submit_for_review(old_request)
        reminded = await review_gate.check_timeouts()
        # Should trigger final timeout since elapsed > timeout_seconds
        assert "req-old" in reminded

    async def test_final_timeout_when_exceeded(self, review_gate):
        """Final timeout reminder when total timeout is exceeded."""
        expired_request = ReviewRequest(
            request_id="req-expired",
            workflow_id="wf-002",
            agent_name="testscript_agent",
            content={"script": "code"},
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            timeout_seconds=60,
        )
        await review_gate.submit_for_review(expired_request)
        reminded = await review_gate.check_timeouts()
        assert "req-expired" in reminded


# =============================================================================
# Test: Configuration Loading
# =============================================================================


class TestConfiguration:
    """Tests for review configuration loading and querying."""

    def test_get_review_config_existing_workflow(self, review_gate):
        """Should return config for a configured workflow."""
        config = review_gate.get_review_config("test_case_generation")
        assert config is not None
        assert "review_points" in config
        assert len(config["review_points"]) == 1
        assert config["review_points"][0]["after_agent"] == "testcase_agent"

    def test_get_review_config_unknown_workflow(self, review_gate):
        """Should return None for an unconfigured workflow."""
        config = review_gate.get_review_config("unknown_workflow")
        assert config is None

    def test_is_review_required_true(self, review_gate):
        """Should return True when review is required."""
        assert review_gate.is_review_required(
            "test_case_generation", "testcase_agent"
        )

    def test_is_review_required_false_wrong_agent(self, review_gate):
        """Should return False for a non-review agent."""
        assert not review_gate.is_review_required(
            "test_case_generation", "other_agent"
        )

    def test_is_review_required_false_unknown_workflow(self, review_gate):
        """Should return False for an unknown workflow."""
        assert not review_gate.is_review_required("unknown", "testcase_agent")

    def test_get_timeout_for_review_point(self, review_gate):
        """Should return configured timeout for a review point."""
        timeout = review_gate.get_timeout_for_review_point(
            "test_case_generation", "testcase_agent"
        )
        assert timeout == 3600

    def test_get_timeout_for_script_review(self, review_gate):
        """Should return configured timeout for script review."""
        timeout = review_gate.get_timeout_for_review_point(
            "test_script_generation", "testscript_agent"
        )
        assert timeout == 7200

    def test_get_timeout_default_for_unknown(self, review_gate):
        """Should return default timeout for unknown workflow."""
        timeout = review_gate.get_timeout_for_review_point(
            "unknown_workflow", "some_agent"
        )
        assert timeout == 3600


# =============================================================================
# Test: Review Record Completeness
# =============================================================================


class TestRecordCompleteness:
    """Tests ensuring review records contain all required fields."""

    async def test_decision_has_reviewer_id(
        self, review_gate, sample_request, sample_approval
    ):
        """Recorded decision must have a reviewer_id."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_approval)
        decision = await review_gate.get_decision("req-001")
        assert decision.reviewer_id is not None
        assert decision.reviewer_id != ""

    async def test_decision_has_timestamp(
        self, review_gate, sample_request, sample_approval
    ):
        """Recorded decision must have a timestamp."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_approval)
        decision = await review_gate.get_decision("req-001")
        assert decision.timestamp is not None
        assert isinstance(decision.timestamp, datetime)

    async def test_decision_has_comments(
        self, review_gate, sample_request, sample_approval
    ):
        """Recorded decision must have comments."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_approval)
        decision = await review_gate.get_decision("req-001")
        assert decision.comments is not None

    async def test_rejection_has_all_fields(
        self, review_gate, sample_request, sample_rejection
    ):
        """Rejection record must have all required fields populated."""
        await review_gate.submit_for_review(sample_request)
        await review_gate.record_decision(sample_rejection)
        decision = await review_gate.get_decision("req-001")
        assert decision.request_id == "req-001"
        assert decision.reviewer_id == "reviewer-bob"
        assert decision.decision == ReviewDecision.REJECTED
        assert decision.comments == "Missing edge case for empty input."
        assert decision.timestamp is not None


# =============================================================================
# Test: Config file loading
# =============================================================================


class TestConfigFileLoading:
    """Tests for loading config from YAML file."""

    def test_load_from_yaml_file(self, tmp_path):
        """Should load configuration from a YAML file."""
        config_file = tmp_path / "review_gates.yaml"
        config_file.write_text(
            """
review_gates:
  workflows:
    my_workflow:
      review_points:
        - after_agent: "my_agent"
          required: true
          timeout_seconds: 1800
  notifications:
    reminder_interval_seconds: 900
    channels:
      - type: "webhook"
        url: "https://hooks.example.com/review"
"""
        )
        gate = HumanReviewGate(config_path=config_file)
        assert gate.is_review_required("my_workflow", "my_agent")
        assert gate.get_timeout_for_review_point("my_workflow", "my_agent") == 1800
        assert gate._reminder_interval_seconds == 900

    def test_load_missing_file_returns_empty_config(self, tmp_path):
        """Should handle missing config file gracefully."""
        gate = HumanReviewGate(config_path=tmp_path / "nonexistent.yaml")
        assert not gate.is_review_required("any_workflow", "any_agent")

    def test_load_empty_config(self):
        """Should handle empty config dict."""
        gate = HumanReviewGate(review_config={})
        assert not gate.is_review_required("any_workflow", "any_agent")
        assert gate.get_review_config("any_workflow") is None
