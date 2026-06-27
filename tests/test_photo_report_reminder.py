"""Unit tests for photo report reminder functionality.

Tests the reminders module and its integration with route command handlers.
Requirements: 8.1, 8.2, 8.3, 8.4
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from promouters.integrations.vk_bot.reminders import (
    MAX_RETRIES,
    PHOTO_REMINDER_MESSAGE,
    RETRY_INTERVAL_SECONDS,
    _send_reminder_with_retries,
    send_photo_report_reminder,
)


class TestSendPhotoReportReminder:
    """Tests for the send_photo_report_reminder function."""

    def test_skip_when_vk_id_is_none(self, caplog):
        """Requirement 8.4: Skip sending reminder if promoter has no VK user ID."""
        with patch(
            "promouters.integrations.vk_bot.reminders.threading.Thread"
        ) as mock_thread:
            send_photo_report_reminder(None)
            mock_thread.assert_not_called()
        assert "no linked VK user ID" in caplog.text

    def test_skip_when_vk_id_is_empty_string(self, caplog):
        """Requirement 8.4: Skip sending reminder if VK user ID is empty."""
        with patch(
            "promouters.integrations.vk_bot.reminders.threading.Thread"
        ) as mock_thread:
            send_photo_report_reminder("")
            mock_thread.assert_not_called()
        assert "no linked VK user ID" in caplog.text

    def test_skip_when_vk_id_is_invalid(self, caplog):
        """Skip sending reminder if VK user ID cannot be converted to int."""
        with patch(
            "promouters.integrations.vk_bot.reminders.threading.Thread"
        ) as mock_thread:
            send_photo_report_reminder("not-a-number")
            mock_thread.assert_not_called()
        assert "invalid VK user ID" in caplog.text

    def test_starts_background_thread_with_valid_vk_id(self):
        """Requirement 8.1: Reminder is sent in a background thread (non-blocking)."""
        with patch(
            "promouters.integrations.vk_bot.reminders.threading.Thread"
        ) as mock_thread_cls:
            mock_thread_instance = MagicMock()
            mock_thread_cls.return_value = mock_thread_instance

            send_photo_report_reminder("12345")

            mock_thread_cls.assert_called_once_with(
                target=_send_reminder_with_retries,
                args=(12345,),
                daemon=True,
                name="photo-reminder-12345",
            )
            mock_thread_instance.start.assert_called_once()

    def test_accepts_integer_vk_id(self):
        """Works when vk_id is passed as an integer."""
        with patch(
            "promouters.integrations.vk_bot.reminders.threading.Thread"
        ) as mock_thread_cls:
            mock_thread_instance = MagicMock()
            mock_thread_cls.return_value = mock_thread_instance

            send_photo_report_reminder(67890)

            mock_thread_cls.assert_called_once_with(
                target=_send_reminder_with_retries,
                args=(67890,),
                daemon=True,
                name="photo-reminder-67890",
            )
            mock_thread_instance.start.assert_called_once()


class TestSendReminderWithRetries:
    """Tests for the _send_reminder_with_retries function."""

    @patch("promouters.integrations.vk_bot.reminders._get_random_id", return_value=12345678)
    @patch("promouters.integrations.vk_bot.reminders.time.sleep")
    def test_successful_first_attempt(self, mock_sleep, mock_random_id):
        """Requirement 8.1: Successfully sends reminder on first attempt."""
        mock_vk = MagicMock()
        with patch(
            "promouters.services.vk_notify._get_vk", return_value=mock_vk
        ):
            result = _send_reminder_with_retries(12345)

        assert result is True
        mock_vk.messages.send.assert_called_once()
        call_kwargs = mock_vk.messages.send.call_args[1]
        assert call_kwargs["user_id"] == 12345
        assert call_kwargs["message"] == PHOTO_REMINDER_MESSAGE
        assert call_kwargs["random_id"] == 12345678
        mock_sleep.assert_not_called()

    @patch("promouters.integrations.vk_bot.reminders._get_random_id", return_value=12345678)
    @patch("promouters.integrations.vk_bot.reminders.time.sleep")
    def test_retries_on_failure(self, mock_sleep, mock_random_id):
        """Requirement 8.3: Retries up to 2 additional attempts on failure."""
        mock_vk = MagicMock()
        mock_vk.messages.send.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            None,  # Success on third attempt
        ]
        with patch(
            "promouters.services.vk_notify._get_vk", return_value=mock_vk
        ):
            result = _send_reminder_with_retries(12345)

        assert result is True
        assert mock_vk.messages.send.call_count == 3
        # Should sleep between retries (2 times: after 1st and 2nd failures)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(RETRY_INTERVAL_SECONDS)

    @patch("promouters.integrations.vk_bot.reminders._get_random_id", return_value=12345678)
    @patch("promouters.integrations.vk_bot.reminders.time.sleep")
    def test_fails_after_all_retries_exhausted(self, mock_sleep, mock_random_id, caplog):
        """Requirement 8.3: Logs failure after all retry attempts exhausted."""
        mock_vk = MagicMock()
        mock_vk.messages.send.side_effect = Exception("Persistent error")
        with patch(
            "promouters.services.vk_notify._get_vk", return_value=mock_vk
        ):
            result = _send_reminder_with_retries(12345)

        assert result is False
        assert mock_vk.messages.send.call_count == MAX_RETRIES + 1
        assert mock_sleep.call_count == MAX_RETRIES
        assert "delivery failed after" in caplog.text

    @patch("promouters.integrations.vk_bot.reminders._get_random_id", return_value=12345678)
    @patch("promouters.integrations.vk_bot.reminders.time.sleep")
    def test_succeeds_on_second_attempt(self, mock_sleep, mock_random_id):
        """Requirement 8.3: Retries and succeeds on second attempt."""
        mock_vk = MagicMock()
        mock_vk.messages.send.side_effect = [
            Exception("Temporary error"),
            None,  # Success on second attempt
        ]
        with patch(
            "promouters.services.vk_notify._get_vk", return_value=mock_vk
        ):
            result = _send_reminder_with_retries(12345)

        assert result is True
        assert mock_vk.messages.send.call_count == 2
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(RETRY_INTERVAL_SECONDS)

    @patch("promouters.integrations.vk_bot.reminders.time.sleep")
    def test_vk_api_not_available(self, mock_sleep, caplog):
        """Handles case when VK API is not initialized (no token)."""
        with patch(
            "promouters.services.vk_notify._get_vk", return_value=None
        ):
            result = _send_reminder_with_retries(12345)

        assert result is False
        assert mock_sleep.call_count == MAX_RETRIES
        assert "VK API not available" in caplog.text

    def test_message_content_is_text_only(self):
        """Requirement 8.2: Reminder is sent as a text-only message."""
        assert PHOTO_REMINDER_MESSAGE == "Скинь фотоотчёт куратору"

    def test_retry_interval_is_30_seconds(self):
        """Requirement 8.3: 30-second interval between retry attempts."""
        assert RETRY_INTERVAL_SECONDS == 30

    def test_max_retries_is_2(self):
        """Requirement 8.3: Up to 2 additional attempts (3 total)."""
        assert MAX_RETRIES == 2
