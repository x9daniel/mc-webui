"""
Read Status Manager - Server-side storage for message read status

Manages the last seen timestamps for channels and DM conversations,
providing cross-device synchronization for unread message tracking.
"""

import json
import logging
import os
from pathlib import Path
from threading import Lock
from app.config import config

logger = logging.getLogger(__name__)

# Thread-safe lock for file operations
_status_lock = Lock()

# Path to read status file
READ_STATUS_FILE = Path(config.MC_CONFIG_DIR) / '.read_status.json'


def _get_default_status():
    """Get default read status structure"""
    return {
        'channels': {},          # {"0": timestamp, "1": timestamp, ...}
        'dm': {},                # {"name_User1": timestamp, "pk_abc123": timestamp, ...}
        'muted_channels': []     # [2, 5, 7] - channel indices with muted notifications
    }


def load_read_status():
    """
    Load read status from disk.

    Returns:
        dict: Read status with 'channels' and 'dm' keys
    """
    with _status_lock:
        try:
            if not READ_STATUS_FILE.exists():
                logger.info("Read status file does not exist, creating default")
                return _get_default_status()

            with open(READ_STATUS_FILE, 'r', encoding='utf-8') as f:
                status = json.load(f)

            # Validate structure
            if not isinstance(status, dict):
                logger.warning("Invalid read status structure, resetting")
                return _get_default_status()

            # Ensure all keys exist
            if 'channels' not in status:
                status['channels'] = {}
            if 'dm' not in status:
                status['dm'] = {}
            if 'muted_channels' not in status:
                status['muted_channels'] = []

            logger.debug(f"Loaded read status: {len(status['channels'])} channels, {len(status['dm'])} DM conversations")
            return status

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse read status file: {e}")
            return _get_default_status()
        except Exception as e:
            logger.error(f"Error loading read status: {e}")
            return _get_default_status()


def save_read_status(status):
    """
    Save read status to disk.

    Args:
        status (dict): Read status with 'channels' and 'dm' keys

    Returns:
        bool: True if successful, False otherwise
    """
    with _status_lock:
        try:
            # Ensure directory exists
            READ_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically (write to temp file, then rename)
            temp_file = READ_STATUS_FILE.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2)

            # Atomic rename
            temp_file.replace(READ_STATUS_FILE)

            logger.debug(f"Saved read status: {len(status['channels'])} channels, {len(status['dm'])} DM conversations")
            return True

        except Exception as e:
            logger.error(f"Error saving read status: {e}")
            return False


def mark_channel_read(channel_idx, timestamp):
    """
    Mark a channel as read up to a specific timestamp.

    Args:
        channel_idx (int or str): Channel index (will be converted to string)
        timestamp (int or float): Unix timestamp of last read message

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load current status
        status = load_read_status()

        # Update channel timestamp (ensure key is string for JSON compatibility)
        channel_key = str(channel_idx)
        status['channels'][channel_key] = int(timestamp)

        # Save updated status
        success = save_read_status(status)

        if success:
            logger.debug(f"Marked channel {channel_idx} as read at timestamp {timestamp}")

        return success

    except Exception as e:
        logger.error(f"Error marking channel {channel_idx} as read: {e}")
        return False


def mark_dm_read(conversation_id, timestamp):
    """
    Mark a DM conversation as read up to a specific timestamp.

    Args:
        conversation_id (str): Conversation identifier (e.g., "name_User1" or "pk_abc123")
        timestamp (int or float): Unix timestamp of last read message

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load current status
        status = load_read_status()

        # Update DM timestamp
        status['dm'][conversation_id] = int(timestamp)

        # Save updated status
        success = save_read_status(status)

        if success:
            logger.debug(f"Marked DM conversation {conversation_id} as read at timestamp {timestamp}")

        return success

    except Exception as e:
        logger.error(f"Error marking DM conversation {conversation_id} as read: {e}")
        return False


def get_channel_last_seen(channel_idx):
    """
    Get last seen timestamp for a specific channel.

    Args:
        channel_idx (int or str): Channel index

    Returns:
        int: Unix timestamp, or 0 if never seen
    """
    try:
        status = load_read_status()
        channel_key = str(channel_idx)
        return status['channels'].get(channel_key, 0)
    except Exception as e:
        logger.error(f"Error getting last seen for channel {channel_idx}: {e}")
        return 0


def get_dm_last_seen(conversation_id):
    """
    Get last seen timestamp for a specific DM conversation.

    Args:
        conversation_id (str): Conversation identifier

    Returns:
        int: Unix timestamp, or 0 if never seen
    """
    try:
        status = load_read_status()
        return status['dm'].get(conversation_id, 0)
    except Exception as e:
        logger.error(f"Error getting last seen for DM {conversation_id}: {e}")
        return 0


def get_muted_channels():
    """
    Get list of muted channel indices.

    Returns:
        list: List of muted channel indices (integers)
    """
    try:
        status = load_read_status()
        return status.get('muted_channels', [])
    except Exception as e:
        logger.error(f"Error getting muted channels: {e}")
        return []


def set_channel_muted(channel_idx, muted):
    """
    Set mute state for a channel.

    Args:
        channel_idx (int): Channel index
        muted (bool): True to mute, False to unmute

    Returns:
        bool: True if successful
    """
    try:
        status = load_read_status()
        muted_list = status.get('muted_channels', [])
        channel_idx = int(channel_idx)

        if muted and channel_idx not in muted_list:
            muted_list.append(channel_idx)
        elif not muted and channel_idx in muted_list:
            muted_list.remove(channel_idx)

        status['muted_channels'] = muted_list
        success = save_read_status(status)

        if success:
            logger.info(f"Channel {channel_idx} {'muted' if muted else 'unmuted'}")
        return success

    except Exception as e:
        logger.error(f"Error setting mute for channel {channel_idx}: {e}")
        return False


def mark_all_channels_read(channel_timestamps):
    """
    Mark all channels as read in bulk.

    Args:
        channel_timestamps (dict): {"0": timestamp, "1": timestamp, ...}

    Returns:
        bool: True if successful
    """
    try:
        status = load_read_status()

        for channel_key, timestamp in channel_timestamps.items():
            status['channels'][str(channel_key)] = int(timestamp)

        success = save_read_status(status)

        if success:
            logger.info(f"Marked {len(channel_timestamps)} channels as read")
        return success

    except Exception as e:
        logger.error(f"Error marking all channels as read: {e}")
        return False
