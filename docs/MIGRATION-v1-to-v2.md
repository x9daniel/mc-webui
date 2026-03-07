# Migration Guide: v1 to v2

## Overview

v2 replaces the `meshcore-cli` bridge with direct `meshcore` library communication. This changes how contacts and DMs work at a fundamental level.

## Breaking Changes

### 1. DM contacts must exist on the device firmware

**Symptom**: Sending a DM to an existing contact fails with "Contact not on device".

**Why**: In v2, `meshcore` communicates directly with the device firmware, which **requires** the contact to exist in its internal contact table (max 350 entries) to send a DM. The mc-webui database may contain hundreds of contacts from advertisement history, but only a handful are actually present on the device.

This can happen after:
- **Firmware reflash** — wipes the device contact table while the DB retains all contacts
- **Migration from v1** — v1 `meshcore-cli` bridge managed contacts independently; many DB contacts may have never been added to the device
- **Device reset** — any factory reset clears the firmware contact table

**How to verify**: Check the startup log for `Synced N contacts from device to database`. This N is the actual number of contacts on the device — likely much smaller than the total in the DB.

**Fix**: For each contact you want to DM:
1. Delete the contact from the Contacts page
2. Wait for their next advertisement
3. Approve the contact when it appears in the pending list

This adds the contact to the device's firmware table, enabling DM sending.

**Note**: Incoming DMs from any contact still work regardless — this only affects *sending* DMs.

### 2. Contact soft-delete preserves DM history

In v2, deleting a contact is a soft-delete (marked as `source='deleted'` in the database). This preserves DM conversation history. When the contact is re-added, it automatically "undeletes" and all previous DMs are visible again.

### 3. Database schema

v2 uses SQLite with WAL mode instead of flat JSON files. The migration from v1 data happens automatically on first startup (see `app/migrate_v1.py`). The v1 data files are preserved and not modified.

## Post-Migration Checklist

- [ ] Verify device connection (green "Connected" indicator)
- [ ] Check that channel messages are flowing normally
- [ ] Check startup log: `Synced N contacts from device to database` — this is your actual device contact count
- [ ] For each DM contact you need: delete, wait for advert, re-approve
- [ ] Verify DM sending works with a test message
